
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from flask import Flask, render_template, request, redirect, url_for, send_file
import threading
import pika
import json
from collections import deque
import time
import openai
import os
from flask import jsonify
from anthropic import Anthropic
import pyttsx3
import speech_recognition as sr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from fpdf import FPDF
import requests

app = Flask(__name__)
vitals_window = deque(maxlen=5)
current_profile = "A"
current_ai = "ChatGPT (OpenAI)"
alert_vital = None
alert_triggered = False
voice_prompted = False
user_response = ""
last_summary = ""
last_insight = ""
last_voice_log = ""

profile_info = {
    "A": {
        "name": "Person A",
        "email": "dharavathjayanth21@gmail.com",
        "age": 62,
        "status": "Generally healthy, active jogger",
        "medical": "No chronic illnesses"
    },
    "B": {
        "name": "Person B",
        "email": "dharavathjayanth21@gmail.com",
        "age": 92,
        "status": "Frail, dependent, poor health",
        "medical": "Hypertension, cardiovascular issues"
    }
}
openai.api_key = 
anthropic_client = 

EMAIL_USER = "crazyjayanth21@gmail.com"
EMAIL_PASS = "buye rkwv mzyh ivyc"

def speak(text):
    engine = pyttsx3.init()
    engine.setProperty('rate', 135)
    engine.say(text)
    engine.runAndWait()

def listen_for_response(timeout=30):
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=timeout)
            return recognizer.recognize_google(audio).lower()
        except Exception as e:
            print(f"\U0001F3A4 Voice error: {e}")
            return ""

def send_email(to_email, subject, body, attachment_path=None):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body.encode('utf-8'), "plain", "utf-8"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as file:
            part = MIMEApplication(file.read(), Name=os.path.basename(attachment_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"\U0001F4E7 Email sent: {subject}")
    except Exception as e:
        print(f"\u274C Email failed: {e}")

def is_critical(v):
    return v['spo2'] < 88 or v['heart_rate'] > 135 or v['bp_sys'] > 180

def get_ip_location():
    try:
        res = requests.get("https://ipinfo.io/json")
        data = res.json()
        return f"{data.get('city')}, {data.get('region')} ({data.get('ip')})"
    except:
        return "Unknown Location"

def get_ai_response(vitals, profile, mode="insight"):
    if mode == "summary":
        prompt = f"""
You are an AI assistant. {profile['name']} ({profile['age']} years) just had a critical health event.
Vitals:
- SpO2: {vitals['spo2']}%
- Heart Rate: {vitals['heart_rate']} bpm
- Blood Pressure: {vitals['bp_sys']}/{vitals['bp_dia']}

Write an emergency summary with recommendations.
"""
    else:
        prompt = f"""
You are an AI assistant. {profile['name']} ({profile['age']} years) experienced minor vital irregularities.
Vitals:
- SpO2: {vitals['spo2']}%
- Heart Rate: {vitals['heart_rate']} bpm
- Blood Pressure: {vitals['bp_sys']}/{vitals['bp_dia']}

Provide personalized lifestyle advice.
"""

    if current_ai == "ChatGPT (OpenAI)":
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return res['choices'][0]['message']['content']
    else:
        res = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.content[0].text

def generate_pdf_report():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Health AI Summary Report", ln=True, align="C")
    pdf.ln(10)
    pdf.multi_cell(0, 10, f"Profile: {profile_info[current_profile]['name']} ({profile_info[current_profile]['age']} years)")
    pdf.multi_cell(0, 10, f"AI Model: {current_ai}")
    pdf.ln(5)
    if last_summary:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="Emergency Summary:", ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, last_summary)
        pdf.ln(5)
    if last_insight:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="AI Health Insight:", ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, last_insight)
        pdf.ln(5)
    if last_voice_log:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="Voice Transcript:", ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, last_voice_log)

    filepath = "health_report.pdf"
    pdf.output(filepath)
    return filepath

@app.route("/download_report")
def download_report():
    filepath = generate_pdf_report()
    return send_file(filepath, as_attachment=True)

@app.route("/respond", methods=["POST"])
def respond():
    global user_response
    user_response = request.form.get("response", "")
    return redirect(url_for("index"))

@app.route('/api/vitals')
def get_vitals():
    print("📤 API returning:", list(vitals_window))
    return jsonify(list(vitals_window))


@app.route("/", methods=["GET", "POST"])
def index():
    global current_profile, current_ai, alert_triggered, voice_prompted, user_response, last_summary, last_insight

    if request.method == "POST":
        current_profile = request.form.get("profile")
        current_ai = request.form.get("ai_model")
        return redirect(url_for("index"))

    profile = profile_info[current_profile]
    return render_template("index.html", vitals=list(vitals_window), profile=profile,
                           current_profile=current_profile, current_ai=current_ai,
                           alert=alert_triggered, last_summary=last_summary,
                           last_insight=last_insight, last_voice_log=last_voice_log,
                           fallback_enabled=True)

def callback(ch, method, properties, body):
    global alert_triggered, alert_vital, voice_prompted, user_response, last_summary, last_insight, last_voice_log

    try:
        vitals = json.loads(body.decode("utf-8"))
    except Exception as e:
        print("❌ Decode Error:", e)
        return

    print("📥 Received:", vitals)
    vitals_window.append(vitals)

    if is_critical(vitals):
        profile = profile_info[current_profile]
        alert_triggered = True
        alert_vital = vitals
        vitals['ai'] = current_ai
        speak("Are you okay? Please respond within 30 seconds or click 'I'm okay' on screen.")
        response = listen_for_response(timeout=30)
        if not response and user_response:
            response = user_response.lower()
        user_response = response
        last_voice_log = response

        
        if any(phrase in response for phrase in ["i am okay", "i'm okay", "yes", "ok", "okay"]):
            print("Response: I'm okay")
            speak("Thank you for your response. Stay healthy!")
            last_insight = get_ai_response(vitals, profile, mode="insight")
            print("Insight:\n", last_insight)
            full_msg = f"Location: {get_ip_location()}\n\n{last_insight}"
            pdf_path = generate_pdf_report()
            send_email(profile['email'], f"✅ Health Update: {profile['name']} is Okay", full_msg, attachment_path=pdf_path)
        else:
            print("No valid response. Sending alert.")
            speak("No response detected. Sending alert to caregiver now.")
            last_summary = get_ai_response(vitals, profile, mode="summary")
            location = get_ip_location()
            full_msg = f"Location: {location}\n\n{last_summary}"
            pdf_path = generate_pdf_report()
            send_email(profile['email'], f"🚨 Emergency Alert for {profile['name']}", full_msg, attachment_path=pdf_path)
            speak("I have notified your emergency contact. I will stay with you. Just say 'I am all right, bye' when you're okay.")
            while True:
                response = listen_for_response(timeout=30)
                if any(phrase in response for phrase in ["i am all right", "bye", "thank you"]):
                    speak("Good to hear you're feeling better. Take care!")
                    break
                else:
                    speak("I'm still here with you. Let me know when you're okay.")

def start_consumer():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='health_data')
        channel.basic_consume(queue='health_data', on_message_callback=callback, auto_ack=True)
        print("✅ RabbitMQ consumer running...")
        channel.start_consuming()
    except Exception as e:
        print("❌ RabbitMQ error:", e)

threading.Thread(target=start_consumer, daemon=True).start()

if __name__ == "__main__":
    app.run(port=5001, host='0.0.0.0')

