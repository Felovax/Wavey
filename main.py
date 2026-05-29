import os
import time
import concurrent.futures
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from google import genai
from google.genai import types
from dotenv import load_dotenv
import security
from llm import *
from llm import _get_client_ip
import requests
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-in-production")


@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "frame-ancestors https://ewaves.no/"
    return response

def wp_login(username, password):
    url = "https://ewaves.no/wp-json/jwt-auth/v1/token"
    response = requests.post(url, json={
        "username": username,
        "password": password
    })

    if response.status_code != 200:
        return None

    return response.json()

# --------------------------------------------------
# Authentication
# --------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_token" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_wp(username, password):
    """Authenticate admin user using WordPress JWT"""
    result = wp_login(username, password)
    if result and "token" in result:
        return result
    return None

# --------------------------------------------------
# Routes
# --------------------------------------------------


import logging
logger = logging.getLogger(__name__)
 
@app.route("/query", methods=["POST", "GET"])
def query():
    try:
        if request.method == "POST":
            user_query = (request.form.get ("query") or "").strip()
        else:
            user_query = request.args.get("query", "").strip()
 
        if not user_query:
            return jsonify({"response": "Vennligst skriv et spørsmål"}), 400
 
        client_ip = _get_client_ip(request)
 
        try:
            sec_result = security.analyze_query(user_query, client_ip)
        except ValueError:
            return jsonify({"response": "Spørsmålet ditt kunne ikke behandles"}), 400
        except Exception as e:
            logger.error(f"Security check failed: {e}")
            return jsonify({"response": "Spørsmålet ditt kunne ikke behandles"}), 400
 
        if sec_result.blocked:
            return jsonify({"response": "Forespørselen ble blokkert"}), 403
 
        if sec_result.limited:
            time.sleep(2)
 
        try:
            answer = generate_website_answer(sec_result.sanitized_query)
            return jsonify({
                "response": answer,
                "risk": sec_result.score,
                "decision": sec_result.decision
            }), 200
 
        except TimeoutError:
            return jsonify({
                "response": "Spørsmålet ditt tok for lang tid. Vennligst prøv igjen.",
                "error": "timeout"
            }), 504
 
        except Exception as e:
            logger.exception(f"Error generating answer: {e}")
            return jsonify({"response": "En feil oppstod ved behandling av spørsmålet"}), 500
 
    except Exception as e:
        logger.exception(f"Unexpected error in /query: {e}")
        return jsonify({"error": "Internal server error"}), 500
 
 


@app.route("/")
def home():
    return render_template("index.html")

# --------------------------------------------------
# ADMIN (unchanged)
# --------------------------------------------------

@app.route("/admin/login", methods=["GET"])
def admin_login():
    """Display login form"""
    return render_template("admin_login.html")

@app.route("/admin/login", methods=["POST"])
def admin_login_post():
    """Handle login submission"""
    username = request.form.get("username")
    password = request.form.get("password")
    
    if not username or not password:
        return render_template("admin_login.html", error="Username and password required"), 400
    
    auth_result = admin_login_wp(username, password)
    
    if not auth_result:
        return render_template("admin_login.html", error="Invalid credentials"), 401
    
    # Store token in session
    session["admin_token"] = auth_result.get("token")
    session["admin_user"] = username
    
    return redirect(url_for("admin_page"))

@app.route("/admin/logout")
def admin_logout():
    """Logout user"""
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_page():
    try:
        files = client.file_search_stores.documents.list(
            parent=FILE_SEARCH_STORE_NAME
        )

        def format_size(bytes_size):
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if bytes_size < 1024:
                    return f"{bytes_size:.2f} {unit}"
                bytes_size /= 1024
            return f"{bytes_size:.2f} PB"

        total_size_bytes = sum(getattr(f, "size_bytes", 0) for f in files)
        total_size_formatted = format_size(total_size_bytes)

        return render_template("admin.html", files=files, total_size=total_size_formatted)
    except Exception:
        return render_template("admin.html", files=[])


@app.route("/admin/files", methods=["GET"])
@login_required
def list_files():
    try:
        files = client.file_search_stores.documents.list(
            parent=FILE_SEARCH_STORE_NAME
        )

        file_list = [
            {
                "name": f.name,
                "display_name": getattr(f, "display_name", None),
                "state": getattr(f, "state", None),
            }
            for f in files
        ]

        return jsonify({"files": file_list})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No filename"}), 400

    try:
        os.makedirs("temp_uploads", exist_ok=True)
        temp_path = os.path.join("temp_uploads", secure_filename(file.filename))

        file.save(temp_path)

        try:
            client.file_search_stores.upload_to_file_search_store(
                file=temp_path,
                file_search_store_name=FILE_SEARCH_STORE_NAME,
                config={"display_name": file.filename},
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return jsonify({"message": "Upload successful"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/files", methods=["DELETE"])
@login_required
def delete_file():
    data = request.get_json()
    file_name = data.get("file_name") if data else None

    if not file_name:
        return jsonify({"error": "Missing file_name"}), 400

    try:
        client.file_search_stores.documents.delete(
            name=file_name,
            config=types.DeleteDocumentConfig(force=True),
        )

        return jsonify({"message": "File deleted"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)