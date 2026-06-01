import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import fitz
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from chatbot import get_chatbot_response
from model import JobRecommendationEngine


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset.csv"
DATABASE_PATH = BASE_DIR / "jobgenie.db"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.secret_key = os.environ.get("JOBGENIE_SECRET_KEY", "jobgenie-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.permanent_session_lifetime = timedelta(days=30)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobgenie")

engine = JobRecommendationEngine(DATASET_PATH)


def error_response(message, status_code=400):
    logger.warning(message)
    return jsonify({"error": message}), status_code


@contextmanager
def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def create_auth_db():
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
            """
        )
        connection.commit()
    print("DEBUG auth database ready:", DATABASE_PATH)


def quarantine_auth_db(reason):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    print("DEBUG auth database repair triggered:", reason)
    for path in (DATABASE_PATH, Path(f"{DATABASE_PATH}-journal")):
        if not path.exists():
            continue
        backup_path = path.with_name(f"{path.name}.corrupt-{timestamp}")
        path.replace(backup_path)
        print("DEBUG auth database file quarantined:", backup_path)


def init_auth_db():
    try:
        create_auth_db()
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "disk i/o" not in message and "database disk image" not in message:
            raise
        quarantine_auth_db(exc)
        create_auth_db()


def public_user(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "initials": "".join(part[0] for part in row["full_name"].split()[:2]).upper(),
    }


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT id, full_name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return public_user(row)


def validate_auth_payload(payload, require_name=False, require_confirm=False):
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if require_name and len(full_name) < 2:
        return "Please enter your full name."
    if not EMAIL_PATTERN.match(email):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if require_confirm and password != confirm_password:
        return "Passwords do not match."
    return ""


init_auth_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/auth/status", methods=["GET"])
def auth_status():
    user = current_user()
    return jsonify({"authenticated": bool(user), "user": user})


@app.route("/signup", methods=["POST"])
def signup():
    payload = request.get_json(silent=True) or {}
    print("DEBUG /signup payload keys:", list(payload.keys()))

    validation_error = validate_auth_payload(payload, require_name=True, require_confirm=True)
    if validation_error:
        return error_response(validation_error, 400)

    full_name = payload["full_name"].strip()
    email = payload["email"].strip().lower()
    password_hash = generate_password_hash(payload["password"])

    try:
        with get_db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                (full_name, email, password_hash),
            )
            connection.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return error_response("An account with this email already exists. Please sign in.", 409)
    except Exception as exc:
        logger.exception("Signup failed")
        return error_response(f"Signup failed: {exc}", 500)

    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["user_email"] = email
    session["user_name"] = full_name

    user = current_user()
    print("DEBUG signup success user_id:", user_id)
    return jsonify({"message": "Account created successfully.", "user": user}), 201


@app.route("/signin", methods=["POST"])
def signin():
    payload = request.get_json(silent=True) or {}
    print("DEBUG /signin payload keys:", list(payload.keys()))

    validation_error = validate_auth_payload(payload)
    if validation_error:
        return error_response(validation_error, 400)

    email = payload["email"].strip().lower()
    password = payload["password"]
    remember = bool(payload.get("remember"))

    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT id, full_name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if not row or not check_password_hash(row["password_hash"], password):
            return error_response("Invalid email or password.", 401)

        connection.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
        connection.commit()

    session.clear()
    session.permanent = remember
    session["user_id"] = row["id"]
    session["user_email"] = row["email"]
    session["user_name"] = row["full_name"]

    print("DEBUG signin success user_id:", row["id"])
    return jsonify({"message": "Signed in successfully.", "user": public_user(row)})


@app.route("/logout", methods=["POST"])
def logout():
    print("DEBUG /logout user_id:", session.get("user_id"))
    session.clear()
    return jsonify({"message": "Logged out successfully."})


@app.route("/upload", methods=["POST"])
def upload_resume():
    print("DEBUG /upload request.files:", request.files)

    if "resume" not in request.files:
        return error_response("No resume file was sent. Please choose a PDF resume.", 400)

    file = request.files["resume"]
    print("DEBUG uploaded filename:", file.filename)
    print("DEBUG uploaded content type:", file.content_type)

    if not file or not file.filename:
        return error_response("The uploaded file is empty or missing a filename.", 400)

    filename = file.filename.lower()
    if not filename.endswith(".pdf") or file.mimetype not in {"application/pdf", "application/octet-stream"}:
        return error_response("Only PDF resumes are supported.", 400)

    pdf_bytes = file.read()
    print("DEBUG uploaded bytes:", len(pdf_bytes))

    if not pdf_bytes:
        return error_response("The uploaded PDF is empty.", 400)

    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        return error_response("The uploaded file does not appear to be a valid PDF.", 400)

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            extracted_pages = [page.get_text("text") for page in document]
            extracted_text = "\n".join(extracted_pages).strip()
            page_count = document.page_count
    except Exception as exc:
        logger.exception("PDF extraction failed")
        return error_response(f"Could not read this PDF. Details: {exc}", 422)

    if not extracted_text:
        return error_response(
            "No selectable text was found in this PDF. Please upload a text-based resume PDF.",
            422,
        )

    print("DEBUG extracted characters:", len(extracted_text))
    return jsonify(
        {
            "text": extracted_text,
            "pages": page_count,
            "characters": len(extracted_text),
        }
    )


@app.route("/predict", methods=["POST"])
def predict_jobs():
    payload = request.get_json(silent=True) or {}
    print("DEBUG /predict payload keys:", list(payload.keys()))

    resume_text = (payload.get("text") or "").strip()
    if not resume_text:
        return error_response("Resume text is required for recommendations.", 400)

    try:
        result = engine.recommend(resume_text, top_n=5)
    except Exception as exc:
        logger.exception("Prediction failed")
        return error_response(f"Recommendation engine failed: {exc}", 500)

    print("DEBUG recommendations returned:", len(result.get("recommendations", [])))
    return jsonify(result)


@app.route("/search", methods=["GET"])
def search_jobs():
    query = (request.args.get("q") or "").strip()
    print("DEBUG /search query:", query)

    if not query:
        return error_response("Search query is required.", 400)

    try:
        results = engine.search_jobs(query, limit=8)
    except Exception as exc:
        logger.exception("Search failed")
        return error_response(f"Search failed: {exc}", 500)

    print("DEBUG search results returned:", len(results))
    return jsonify({"query": query, "count": len(results), "results": results})


@app.route("/search_suggestions", methods=["GET"])
def search_suggestions():
    query = (request.args.get("q") or "").strip()
    print("DEBUG /search_suggestions query:", query)

    if not query:
        return jsonify({"query": query, "suggestions": []})

    try:
        suggestions = engine.search_suggestions(query, limit=8)
    except Exception as exc:
        logger.exception("Search suggestions failed")
        return error_response(f"Search suggestions failed: {exc}", 500)

    print("DEBUG suggestions returned:", len(suggestions))
    return jsonify({"query": query, "suggestions": suggestions})


@app.route("/chatbot", methods=["POST"])
def chatbot():
    payload = request.get_json(silent=True) or {}
    print("DEBUG /chatbot payload:", payload)

    message = (payload.get("message") or "").strip()
    context = payload.get("context") or {}

    if not message:
        return error_response("Please type a message for JobGenie.", 400)

    response = get_chatbot_response(message, context)
    return jsonify({"reply": response})


if __name__ == "__main__":
    print("DEBUG starting JobGenie AI on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
