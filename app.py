import os
import csv
import io
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, Response, render_template, request, redirect, url_for, flash, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from PIL import Image, UnidentifiedImageError
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, init_db

app = Flask(__name__)
csrf = CSRFProtect(app)
load_dotenv()
app.secret_key = os.environ["SECRET_KEY"]
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def detect_priority(title, description):
    text = f"{title} {description}".lower()

    high_keywords = [
        "fire", "accident", "emergency",
        "electric shock", "exposed wire",
        "open electric wire", "gas leak",
        "building collapse", "severe flooding",
        "life threatening", "major accident"
    ]

    medium_keywords = [
        "water supply", "water shortage",
        "blocked drainage", "sewage overflow",
        "street light", "water leakage",
        "broken pipe", "drainage problem"
    ]

    if any(word in text for word in high_keywords):
        return "High"

    elif any(word in text for word in medium_keywords):
        return "Medium"

    return "Low"

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter all details. Password must be at least 8 characters.", "danger")
            return render_template("register.html")
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'citizen')",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except Exception:
            conn.rollback()
            flash("This email may already be registered.", "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch citizen complaints
    cur.execute("""
        SELECT
            c.*,
            f.rating AS user_rating,
            f.feedback AS user_feedback
        FROM complaints c
        LEFT JOIN complaint_feedback f
            ON c.id = f.complaint_id
        WHERE c.user_id = %s
        ORDER BY c.created_at DESC
    """, (session["user_id"],))

    complaints = cur.fetchall()

    for complaint in complaints:
        cur.execute("""
            SELECT old_status, new_status, changed_at
            FROM complaint_status_history
            WHERE complaint_id = %s
            ORDER BY changed_at ASC
        """, (complaint["id"],))

        complaint["status_history"] = cur.fetchall()

    # Calculate complaint statistics
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(status = 'Pending'), 0) AS pending,
            COALESCE(SUM(status = 'In Progress'), 0) AS in_progress,
            COALESCE(SUM(status = 'Resolved'), 0) AS resolved
        FROM complaints
        WHERE user_id = %s
    """, (session["user_id"],))

    stats = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "dashboard.html",
        complaints=complaints,
        stats=stats
    )

@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "")
        description = request.form.get("description", "").strip()
        priority = detect_priority(title, description)
        location = request.form.get("location", "").strip()
        latitude = request.form.get("latitude", "").strip()
        longitude = request.form.get("longitude", "").strip()

        try:
            latitude = float(latitude)
            longitude = float(longitude)

            if not (-90 <= latitude <= 90 and
                    -180 <= longitude <= 180):
                raise ValueError

        except (ValueError, TypeError):
            flash("Please select a valid location on the map.", "danger")
            return render_template("report.html")

        image_name = None
        uploaded = request.files.get("image")

        if uploaded and uploaded.filename:

            if not allowed_file(uploaded.filename):
                flash("Only PNG, JPG, JPEG and WEBP images are allowed.", "danger")
                return render_template("report.html")

            try:
                image = Image.open(uploaded.stream)

                actual_format = image.format

                if actual_format not in ["PNG", "JPEG", "WEBP"]:
                    raise ValueError("Invalid image format")

                image.verify()

                uploaded.stream.seek(0)
                image = Image.open(uploaded.stream)

                extension_map = {
                    "PNG": "png",
                    "JPEG": "jpg",
                    "WEBP": "webp"
                }

                import uuid

                image_name = (
                    f"{uuid.uuid4().hex}.{extension_map[actual_format]}"
                )

                save_path = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_name
                )

                image.save(save_path, format=actual_format)

            except (UnidentifiedImageError, OSError, ValueError):
                flash("Invalid image file. Please upload a genuine image.", "danger")
                return render_template("report.html")
        if not all([title, category, description, location]):
            flash("Please complete all required fields.", "danger")
            return render_template("report.html")
        import uuid
        complaint_id = "CP-" + uuid.uuid4().hex[:8].upper()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO complaints
            (
                complaint_code,
                user_id,
                title,
                category,
                description,
                location,
                latitude,
                longitude,
                image,
               status,
               priority
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending',%s)
        """, (
            complaint_id,
            session["user_id"],
            title,
            category,
            description,
            location,
            latitude,
            longitude,
            image_name,
            priority
        ))
        conn.commit()
        cur.close()
        conn.close()
        flash(f"Complaint submitted. Your ID is {complaint_id}.", "success")
        return redirect(url_for("dashboard"))
    return render_template("report.html")

@app.route("/submit-feedback/<int:complaint_id>", methods=["POST"])
@login_required
def submit_feedback(complaint_id):

    rating = request.form.get("rating", type=int)
    feedback = request.form.get("feedback", "").strip()

    if rating not in [1, 2, 3, 4, 5]:
        flash("Please select a valid rating.", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, status
        FROM complaints
        WHERE id = %s AND user_id = %s
    """, (complaint_id, session["user_id"]))

    complaint = cur.fetchone()

    if not complaint:
        cur.close()
        conn.close()
        flash("Complaint not found.", "error")
        return redirect(url_for("dashboard"))

    if complaint["status"] != "Resolved":
        cur.close()
        conn.close()
        flash("Feedback is allowed only for resolved complaints.", "error")
        return redirect(url_for("dashboard"))

    cur.execute("""
        SELECT id FROM complaint_feedback
        WHERE complaint_id = %s
    """, (complaint_id,))

    existing = cur.fetchone()

    if existing:
        cur.close()
        conn.close()
        flash("Feedback has already been submitted.", "error")
        return redirect(url_for("dashboard"))

    cur.execute("""
        INSERT INTO complaint_feedback
        (complaint_id, user_id, rating, feedback)
        VALUES (%s, %s, %s, %s)
    """, (complaint_id, session["user_id"], rating, feedback))

    conn.commit()
    cur.close()
    conn.close()

    flash("Thank you! Your feedback has been submitted.", "success")
    return redirect(url_for("dashboard"))

@app.route("/track", methods=["GET", "POST"])
def track():
    complaint = None
    if request.method == "POST":
        code = request.form.get("complaint_code", "").strip().upper()
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT complaint_code,title,category,location,status,created_at,updated_at FROM complaints WHERE complaint_code=%s", (code,))
        complaint = cur.fetchone()
        cur.close()
        conn.close()
        if not complaint:
            flash("No complaint found with that ID.", "warning")
    return render_template("track.html", complaint=complaint)

@app.route("/admin")
@admin_required
def admin_dashboard():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    category_filter = request.args.get("category", "").strip()

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT c.*, u.name AS citizen_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        WHERE 1=1
    """

    params = []

    if search:
        query += """
            AND (
                c.complaint_code LIKE %s
                OR c.title LIKE %s
                OR u.name LIKE %s
            )
        """
        term = f"%{search}%"
        params.extend([term, term, term])

    if status_filter in ["Pending", "In Progress", "Resolved"]:
        query += " AND c.status = %s"
        params.append(status_filter)

    if category_filter:
        query += " AND c.category = %s"
        params.append(category_filter)

    query += " ORDER BY c.created_at DESC"

    cur.execute(query, tuple(params))
    complaints = cur.fetchall()

    # Prepare map data from complaints having valid coordinates
    map_complaints = []

    for c in complaints:
        if c.get("latitude") is not None and c.get("longitude") is not None:
            map_complaints.append({
                "code": c["complaint_code"],
                "title": c["title"],
                "category": c["category"],
                "location": c["location"],
                "status": c["status"],
                "latitude": float(c["latitude"]),
                "longitude": float(c["longitude"])
            })

    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(status='Pending'), 0) AS pending,
            COALESCE(SUM(status='In Progress'), 0) AS in_progress,
            COALESCE(SUM(status='Resolved'), 0) AS resolved
        FROM complaints
    """)

    stats = cur.fetchone()

    # Category-wise complaint analytics
    cur.execute("""
        SELECT category, COUNT(*) AS total
        FROM complaints
        GROUP BY category
        ORDER BY total DESC
    """)
    category_stats = cur.fetchall()

    # Area-wise complaint analytics
    cur.execute("""
        SELECT location, COUNT(*) AS total
        FROM complaints
        GROUP BY location
        ORDER BY total DESC
        LIMIT 10
    """)
    area_stats = cur.fetchall()

    # Monthly complaint analytics (last 6 months)
    cur.execute("""
        SELECT
            DATE_FORMAT(created_at, '%b %Y') AS month,
            COUNT(*) AS total
        FROM complaints
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY YEAR(created_at), MONTH(created_at), DATE_FORMAT(created_at, '%b %Y')
        ORDER BY YEAR(created_at), MONTH(created_at)
    """)
    monthly_stats = cur.fetchall()

    # Complaint resolution percentage
    total_complaints = stats["total"] or 0
    resolved_complaints = stats["resolved"] or 0

    resolution_rate = (
        round((resolved_complaints / total_complaints) * 100, 1)
        if total_complaints > 0 else 0
    )

    cur.execute("""
        SELECT DISTINCT category
        FROM complaints
        ORDER BY category
    """)

    categories = [row["category"] for row in cur.fetchall()]

    # Fetch complaint feedback
    cur.execute("""
        SELECT
            f.id,
            f.rating,
            f.feedback,
            f.created_at,
            c.complaint_code,
            c.title,
            u.name AS citizen_name
        FROM complaint_feedback f
        JOIN complaints c ON f.complaint_id = c.id
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """)

    feedbacks = cur.fetchall()

    # Calculate average rating
    cur.execute("""
        SELECT
            COUNT(*) AS total_reviews,
            COALESCE(AVG(rating), 0) AS average_rating
        FROM complaint_feedback
    """)

    feedback_stats = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "admin.html",
        complaints=complaints,
        stats=stats,
        categories=categories,
        search=search,
        status_filter=status_filter,
        category_filter=category_filter,
        map_complaints=map_complaints,
        category_stats=category_stats,
        area_stats=area_stats,
        monthly_stats=monthly_stats,
        resolution_rate=resolution_rate,
        feedbacks=feedbacks,
        feedback_stats=feedback_stats
    )

@app.route("/admin/complaint/<int:complaint_id>")
@admin_required
def complaint_details(complaint_id):

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            c.*,
            u.name AS citizen_name,
            u.email AS citizen_email
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = %s
    """, (complaint_id,))

    complaint = cur.fetchone()

    cur.close()
    conn.close()

    if not complaint:
        flash("Complaint not found.", "error")
        return redirect(url_for("admin_dashboard"))

    return render_template(
        "complaint_details.html",
        complaint=complaint
    )

@app.route("/admin/export-csv")
@admin_required
def export_complaints():

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            c.complaint_code,
            u.name AS citizen_name,
            u.email AS citizen_email,
            c.title,
            c.category,
            c.description,
            c.location,
            c.priority,
            c.status,
            c.admin_remark,
            c.created_at
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        ORDER BY c.created_at DESC
    """)

    complaints = cur.fetchall()

    cur.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Complaint ID",
        "Citizen Name",
        "Email",
        "Title",
        "Category",
        "Description",
        "Location",
        "Priority",
        "Status",
        "Admin Remark",
        "Created At"
    ])

    for c in complaints:
        writer.writerow([
            c["complaint_code"],
            c["citizen_name"],
            c["citizen_email"],
            c["title"],
            c["category"],
            c["description"],
            c["location"],
            c["priority"],
            c["status"],
            c["admin_remark"],
            c["created_at"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=CivicPulse_Complaints.csv"
        }
    )

@app.route("/admin/complaint/<int:complaint_id>/status", methods=["POST"])
@admin_required
def update_status(complaint_id):

    status = request.form.get("status")
    admin_remark = request.form.get("admin_remark", "").strip()

    if status not in {"Pending", "In Progress", "Resolved"}:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # Get current complaint status
        cur.execute("""
            SELECT status
            FROM complaints
            WHERE id = %s
        """, (complaint_id,))

        complaint = cur.fetchone()

        if not complaint:
            flash("Complaint not found.", "danger")
            return redirect(url_for("admin_dashboard"))

        old_status = complaint["status"]

        # Update complaint status and remark
        cur.execute("""
            UPDATE complaints
            SET status = %s,
                admin_remark = %s
            WHERE id = %s
        """, (status, admin_remark, complaint_id))

        # Save history only when status actually changes
        if old_status != status:
            cur.execute("""
                INSERT INTO complaint_status_history
                (complaint_id, old_status, new_status, changed_by)
                VALUES (%s, %s, %s, %s)
            """, (
                complaint_id,
                old_status,
                status,
                session["user_id"]
            ))

        conn.commit()
        flash("Complaint updated successfully.", "success")

    except Exception:
        conn.rollback()
        flash("Unable to update complaint. Please try again.", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("admin_dashboard"))

@app.errorhandler(413)
def too_large(_error):
    flash("Image is too large. Maximum size is 5 MB.", "danger")
    return redirect(url_for("report"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
