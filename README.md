# CivicPulse

A beginner-friendly Flask + MySQL civic complaint management starter project.

## Features
- Citizen registration and login (passwords are hashed)
- Submit complaints with category, description, location and optional image
- Unique complaint ID and public status tracking
- Citizen dashboard
- Admin dashboard and complaint status updates

## 1. Requirements
- Python 3.10+
- MySQL Server and MySQL Workbench (or command-line client)
- VS Code (recommended)

## 2. Create and activate a virtual environment
Windows PowerShell:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
Windows CMD:
```bat
python -m venv venv
venv\Scripts\activate
```

## 3. Install packages
```bash
pip install -r requirements.txt
```

## 4. Configure MySQL
Open MySQL Workbench and run `schema.sql`. Then copy `.env.example` to `.env` and enter your MySQL password.

## 5. Run the website
```bash
python app.py
```
Open http://127.0.0.1:5000

## 6. Make an admin account
1. Register through the website.
2. In MySQL Workbench run (replace the email):
```sql
USE civicpulse;
UPDATE users SET role='admin' WHERE email='your-admin-email@example.com';
```
3. Log out and log in again. You will be redirected to `/admin`.

## Project structure
```text
CivicPulse/
├── app.py
├── database.py
├── schema.sql
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── report.html
│   ├── track.html
│   └── admin.html
└── static/
    ├── css/style.css
    ├── js/main.js
    └── uploads/
```

## Notes before deployment
- Change `SECRET_KEY`; never publish your `.env` file.
- Turn `debug=False` in production.
- Add CSRF protection, rate limiting, email verification and stricter upload validation before public deployment.
- The map, notifications and AI categorization are extension features, not included in this starter.
