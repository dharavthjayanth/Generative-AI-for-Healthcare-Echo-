import os
import csv
import io
import boto3
import requests
import openai
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
app.permanent_session_lifetime = timedelta(minutes=30)

'''Uplode Key
AWS_ACCESS_KEY_ID =
AWS_SECRET_ACCESS_KEY = 
AWS_BUCKET_NAME = 
AWS_REGION = 
'''

openai.api_key = ###apikey


ANTHROPIC_API_KEY =  ###apikey

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

USERS = {
    "123": {
        "dataset_key": "Person_A_elevated.csv",
        "person_profile": (
            "Profile:\n"
            "Name: Person A\n"
            "Age: 62 years\n"
            "Health Status: Generally healthy, physically active, regular jogger\n"
            "Medical History: No chronic illnesses, stable vitals, good cardiovascular condition\n"
        ),
        "label": "Person A",
    },
    "101": {
        "dataset_key": "Person_B_elevated.csv",
        "person_profile": (
            "Profile:\n"
            "Name: Person B\n"
            "Age: 92 years\n"
            "Health Status: Frail, advanced age, dependent, poor overall health\n"
            "Medical Conditions:\n"
            "- Hypertension\n"
            "- Likely chronic cardiovascular problems\n"
        ),
        "label": "Person B",
    },
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "authenticated" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def ensure_config():
    
    if request.endpoint in ("login", "authenticate", "static"):
        return

    missing = []
    if not AWS_ACCESS_KEY_ID: missing.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY: missing.append("AWS_SECRET_ACCESS_KEY")
    if not AWS_BUCKET_NAME: missing.append("AWS_BUCKET_NAME")
    if not AWS_REGION: missing.append("AWS_REGION")
    if not (openai.api_key or ANTHROPIC_API_KEY):
        
        missing.append("OPENAI_API_KEY or ANTHROPIC_API_KEY")

    if missing:
        return (
            f"<h3>Server misconfigured. Missing: {', '.join(missing)}</h3>"
            "<p>Set environment variables and restart the server.</p>",
            500,
        )

def fetch_csv_from_s3(file_key):
    """
    Fetch CSV content from AWS S3.
    Returns a list of rows if successful, else a string error message.
    """
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        response = s3.get_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
        content = response["Body"].read().decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        rows = [row for row in csv_reader]
        print(f"[DEBUG] Fetched {len(rows)} rows from S3 for key: {file_key}")
        return rows
    except Exception as e:
        err = f"Error fetching CSV from S3: {str(e)}"
        print("[DEBUG]", err)
        return err

def call_openai_chat(prompt):
    """
    Calls OpenAI ChatCompletion (gpt-3.5-turbo compatible) with the given prompt.
    """
    if not openai.api_key:
        return "OpenAI API key not configured on server."

    print("[DEBUG] Sending prompt to OpenAI:\n", prompt[:1500])  #
    try:
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
        )
        reply = response["choices"][0]["message"]["content"]
        print("[DEBUG] OpenAI reply (truncated):\n", reply[:1000])
        return reply
    except Exception as e:
        err = f"Error calling OpenAI: {str(e)}"
        print("[DEBUG]", err)
        return err

def call_anthropic_chat(prompt):
    """
    Calls Claude (Anthropic) with the given prompt using the v1/messages endpoint.
    """
    if not ANTHROPIC_API_KEY:
        return "Anthropic API key not configured on server."

    print("[DEBUG] Sending prompt to Anthropic:\n", prompt[:2000])  
    headers = {
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
        "X-API-Key": ANTHROPIC_API_KEY
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 400,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=30)
        print("[DEBUG] Anthropic API Status:", resp.status_code)
        if resp.status_code >= 400:
            print("[DEBUG] Anthropic API Body:", resp.text)
        resp.raise_for_status()
        data = resp.json()
        
        content_array = data.get("content", [])
        if content_array and "text" in content_array[0]:
            reply = content_array[0]["text"]
        elif "completion" in data:
            reply = data["completion"]
        else:
            reply = "No text found in Anthropic response."
        print("[DEBUG] Anthropic reply (truncated):\n", reply[:1000])
        return reply
    except Exception as e:
        err = f"Error calling Anthropic: {str(e)}"
        print("[DEBUG]", err)
        return err


@app.route("/")
def login():
    """Render the login page."""
    return render_template("login.html")

@app.route("/authenticate", methods=["POST"])
def authenticate():
    """
    Check the password, set session info, redirect to chat.
    Only allow passwords in USERS (123, 101).
    """
    password = request.form.get("password", "").strip()
    user_info = USERS.get(password)
    print("[DEBUG] User password attempt:", password, "-> allowed:", bool(user_info))

    if user_info:
        session.clear()
        session.permanent = True
        session["authenticated"] = True
        session["dataset_key"] = user_info["dataset_key"]
        session["person_profile"] = user_info["person_profile"]
        session["user_label"] = user_info["label"]
        return redirect(url_for("chat_page"))
    else:
        return render_template("login.html", error="Incorrect password. Please try again.")

@app.route("/chat")
@login_required
def chat_page():
    """Render chat interface page."""
    return render_template(
        "index.html",
        dataset=session.get("dataset_key", ""),
        person_profile=session.get("person_profile", ""),
        user_label=session.get("user_label", "Unknown")
    )

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    """
    Receives JSON:
      { "message": "...", "ai_choice": "openai" or "anthropic" }
    1. Fetch CSV snippet from S3 (based on session dataset).
    2. Combine profile + snippet with user message.
    3. Call chosen AI.
    """
    data = request.get_json() or {}
    user_message = (data.get("message") or "").strip()
    ai_choice = (data.get("ai_choice") or "openai").strip().lower()

    if not user_message:
        return jsonify({"reply": "No message provided."}), 400

    dataset_key = session.get("dataset_key")
    person_profile = (session.get("person_profile") or "").strip()
    if not dataset_key:
        return jsonify({"reply": "No dataset selected."}), 400


    csv_data = fetch_csv_from_s3(dataset_key)
    if isinstance(csv_data, str):
        
        snippet = f"(Could not fetch dataset: {csv_data})"
    else:
        snippet_rows = csv_data[:8640]
        snippet = "\n".join([", ".join(row) for row in snippet_rows])

    combined_prompt = (
        f"{person_profile}\n\n"
        f"User Message:\n{user_message}\n\n"
        f"Context from dataset (first 8640 rows):\n{snippet}"
    )
    print("[DEBUG] Final prompt (truncated):\n", combined_prompt[:2000])

    if ai_choice == "openai":
        ai_reply = call_openai_chat(combined_prompt)
    elif ai_choice == "anthropic":
        ai_reply = call_anthropic_chat(combined_prompt)
    else:
        ai_reply = "Invalid AI choice. Use 'openai' or 'anthropic'."

    return jsonify({"reply": ai_reply})

@app.route("/logout")
def logout():
    """Clear session and redirect to login page."""
    session.clear()
    return redirect(url_for("login"))


@app.errorhandler(404)
def not_found_error(error):
    return "<h2>404 Not Found</h2>", 404

@app.errorhandler(500)
def internal_error(error):
    return "<h2>500 Internal Server Error</h2>", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
