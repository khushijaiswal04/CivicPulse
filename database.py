
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():

    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "civicpulse")
    }

    # Enable SSL for Aiven MySQL
    ssl_ca = os.getenv("DB_SSL_CA")

    if ssl_ca:
        db_config.update({
            "ssl_ca": ssl_ca,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True
        })

    return mysql.connector.connect(**db_config)


def init_db():
    """Create tables if they do not already exist."""

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('citizen','admin') NOT NULL DEFAULT 'citizen',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INT AUTO_INCREMENT PRIMARY KEY,
            complaint_code VARCHAR(20) NOT NULL UNIQUE,
            user_id INT NOT NULL,
            title VARCHAR(150) NOT NULL,
            category VARCHAR(60) NOT NULL,
            description TEXT NOT NULL,
            location VARCHAR(255) NOT NULL,
            image VARCHAR(255),
            status ENUM('Pending','In Progress','Resolved')
                NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
