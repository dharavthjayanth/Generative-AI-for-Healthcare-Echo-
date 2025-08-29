import os
import boto3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify
from fpdf import FPDF
import smtplib
import requests
import openai
import anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json

app = Flask(__name__)

LAST_N_DAYS = 30

AWS_ACCESS_KEY_ID = 
AWS_SECRET_ACCESS_KEY = 
AWS_BUCKET_NAME = 
AWS_REGION = 

EMAIL_USER = os.getenv("EMAIL_USER", "your_email@gmail.com")
EMAIL_PASS = os.getenv("EMAIL_PASS", "your_app_password")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "receiver@example.com")

openai.api_key = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY"))

PERSONS = {
    "a": {
        "name": "Person A",
        "age": 62,
        "status": "generally healthy, physically active, regular jogger",
        "file": "Person_A_elevated.csv"
    },
    "b": {
        "name": "Person B",
        "age": 92,
        "status": "frail, advanced age, poor overall health with hypertension",
        "file": "Person_B_critical.csv"
    }
}


class PDF(FPDF):
    def header(self):
        self.set_fill_color(50, 90, 130)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 16)
        self.cell(0, 12, self.title, ln=True, align='C', fill=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 9)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, label):
        self.set_fill_color(220, 220, 220)
        self.set_text_color(0)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, label, ln=True, fill=True)
        self.ln(2)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 9, body.encode('latin-1', 'replace').decode('latin-1'))
        self.ln()


def analyze_health_metrics(df):
    """Analyze health data and provide detailed insights (over the filtered month window)."""
    analysis = {}

    hr_avg = df['Heart Rate'].mean()
    hr_max = df['Heart Rate'].max()
    hr_min = df['Heart Rate'].min()

    if hr_avg < 60:
        hr_status = "Low (Bradycardia)"
        hr_color = "warning"
    elif hr_avg > 100:
        hr_status = "High (Tachycardia)"
        hr_color = "danger"
    else:
        hr_status = "Normal"
        hr_color = "success"

    analysis['heart_rate'] = {
        'avg': round(hr_avg, 1),
        'max': float(hr_max),
        'min': float(hr_min),
        'status': hr_status,
        'color': hr_color,
        'trend': get_trend(df['Heart Rate'])
    }

    spo2_avg = df['SpO2'].mean()
    spo2_min = df['SpO2'].min()

    if spo2_avg >= 95:
        spo2_status = "Normal"
        spo2_color = "success"
    elif spo2_avg >= 90:
        spo2_status = "Mild Hypoxemia"
        spo2_color = "warning"
    else:
        spo2_status = "Severe Hypoxemia"
        spo2_color = "danger"

    analysis['spo2'] = {
        'avg': round(spo2_avg, 1),
        'min': float(spo2_min),
        'status': spo2_status,
        'color': spo2_color,
        'trend': get_trend(df['SpO2'])
    }

    sys_avg = df['Systolic BP'].mean()
    dia_avg = df['Diastolic BP'].mean()

    if sys_avg < 120 and dia_avg < 80:
        bp_status = "Normal"
        bp_color = "success"
    elif sys_avg < 130 and dia_avg < 80:
        bp_status = "Elevated"
        bp_color = "warning"
    elif sys_avg < 140 or dia_avg < 90:
        bp_status = "Stage 1 Hypertension"
        bp_color = "warning"
    else:
        bp_status = "Stage 2 Hypertension"
        bp_color = "danger"

    analysis['blood_pressure'] = {
        'systolic_avg': round(sys_avg, 1),
        'diastolic_avg': round(dia_avg, 1),
        'status': bp_status,
        'color': bp_color,
        'sys_trend': get_trend(df['Systolic BP']),
        'dia_trend': get_trend(df['Diastolic BP'])
    }

    health_score = calculate_health_score(analysis)
    analysis['health_score'] = health_score

    return analysis


def get_trend(series):
    """Calculate trend direction using early vs recent slices of the filtered window."""
    if len(series) < 20:
        return "stable"

    recent = series.tail(10).mean()
    older = series.head(10).mean()

    if recent > older * 1.05:
        return "increasing"
    elif recent < older * 0.95:
        return "decreasing"
    else:
        return "stable"


def calculate_health_score(analysis):
    """Calculate overall health score (0-100)"""
    score = 100

    if analysis['heart_rate']['color'] == 'danger':
        score -= 30
    elif analysis['heart_rate']['color'] == 'warning':
        score -= 15

    if analysis['spo2']['color'] == 'danger':
        score -= 40
    elif analysis['spo2']['color'] == 'warning':
        score -= 20

    if analysis['blood_pressure']['color'] == 'danger':
        score -= 30
    elif analysis['blood_pressure']['color'] == 'warning':
        score -= 15

    return max(0, score)


def get_health_recommendations(analysis, person):
    """Generate personalized health recommendations"""
    recommendations = []

    if analysis['heart_rate']['color'] == 'danger':
        if analysis['heart_rate']['avg'] > 100:
            recommendations.append("⚠️ Consult your doctor about elevated heart rate. Consider stress management techniques.")
        else:
            recommendations.append("⚠️ Low heart rate detected. Please consult your healthcare provider.")

    if analysis['spo2']['color'] in ['danger', 'warning']:
        recommendations.append("🫁 Monitor oxygen levels closely. Consider breathing exercises and consult your doctor.")

    if analysis['blood_pressure']['color'] in ['danger', 'warning']:
        recommendations.append("🩺 Blood pressure needs attention. Monitor sodium intake and consider lifestyle changes.")

    if person['age'] > 65:
        recommendations.append("👥 Regular medical check-ups are crucial at your age. Stay active with gentle exercises.")

    if analysis['health_score'] > 80:
        recommendations.append("✅ Your health metrics look good! Keep maintaining your current lifestyle.")
    elif analysis['health_score'] > 60:
        recommendations.append("📈 Some areas need attention. Focus on the highlighted concerns.")
    else:
        recommendations.append("🚨 Please consult your healthcare provider soon for a comprehensive evaluation.")

    return recommendations


def get_location():
    try:
        data = requests.get("https://ipinfo.io/json", timeout=5).json()
        lat, lon = data.get('loc', ',').split(',')
        city = data.get('city', 'Unknown City')
        region = data.get('region', 'Unknown Region')
        country = data.get('country', 'Unknown Country')
        return f"{city}, {region}, {country}\nhttps://www.google.com/maps?q={lat},{lon}\n"
    except Exception:
        return "Location unavailable"


def send_email(subject, body, attachment):
    print("\U0001f4e4 Sending email...")
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body + "\nLocation: " + get_location(), 'plain'))

        if attachment and os.path.exists(attachment):
            with open(attachment, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename=' + os.path.basename(attachment))
                msg.attach(part)

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, RECEIVER_EMAIL, msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Email sending failed: {e}")


def generate_openai_summary(prompt):
    print("\U0001f916 Calling OpenAI...")
    try:
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return "OpenAI failed to respond."


def generate_claude_summary(prompt):
    print("\U0001f916 Calling Claude...")
    try:
        response = claude.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text if response.content else "Claude returned no content."
    except Exception as e:
        print(f"❌ Claude error: {e}")
        return "Claude failed to respond."


def download_csv(person_key):
    print("\U0001f5c2️ Downloading file from S3...")
    try:
        file_key = PERSONS[person_key]["file"]
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        s3.download_file(Bucket=AWS_BUCKET_NAME, Key=file_key, Filename="data.csv")
        print("✅ File downloaded successfully.")
    except Exception as e:
        print(f"❌ Failed to download file: {e}")
        raise


def generate_pdf(person, summary, tips, analysis):
    pdf = PDF()
    pdf.title = "Monthly Health Report"
    pdf.add_page()
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 8, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(5)

    # Health Score Section
    pdf.chapter_title(f"Health Score: {analysis['health_score']}/100")
    score_text = (
        f"Heart Rate: {analysis['heart_rate']['avg']} bpm ({analysis['heart_rate']['status']})\n"
        f"SpO2: {analysis['spo2']['avg']}% ({analysis['spo2']['status']})\n"
        f"Blood Pressure: {analysis['blood_pressure']['systolic_avg']}/"
        f"{analysis['blood_pressure']['diastolic_avg']} mmHg ({analysis['blood_pressure']['status']})"
    )
    pdf.chapter_body(score_text)

    pdf.chapter_title("Detailed Analysis")
    pdf.chapter_body(summary)

    pdf.chapter_title("Personalized Health Tips")
    pdf.chapter_body(tips)

    filename = "Monthly_Report.pdf"
    pdf.output(filename)
    print("📄 PDF generated.")
    return filename


def filter_last_n_days(df, days=LAST_N_DAYS):
    """Filter dataframe to the last N days based on Timestamp."""
    df = df.sort_values('Timestamp')
    if df['Timestamp'].isna().all():
        return df.iloc[0:0] 

    end_date = df['Timestamp'].max()
    start_date = end_date - pd.Timedelta(days=days)
    monthly = df[(df['Timestamp'] >= start_date) & (df['Timestamp'] <= end_date)]
    return monthly if not monthly.empty else df

@app.route('/')
def home():
    return render_template("monthly_report.html")


@app.route('/dashboard/<person_key>')
def dashboard(person_key):
    """Health dashboard showing metrics for the last N days (default 30)."""
    try:
        if person_key not in PERSONS:
            return redirect(url_for('home'))

        person = PERSONS[person_key]
        download_csv(person_key)

        df = pd.read_csv("data.csv")
        df.columns = df.columns.str.strip()
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        df = df.dropna(subset=['Timestamp'])

        
        df = filter_last_n_days(df, LAST_N_DAYS)

        analysis = analyze_health_metrics(df)
        recommendations = get_health_recommendations(analysis, person)

        
        chart_data = {
            'timestamps': df['Timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
            'heart_rate': df['Heart Rate'].tolist(),
            'spo2': df['SpO2'].tolist(),
            'systolic': df['Systolic BP'].tolist(),
            'diastolic': df['Diastolic BP'].tolist()
        }

        return render_template(
            "dashboard.html",
            person=person,
            analysis=analysis,
            recommendations=recommendations,
            chart_data=json.dumps(chart_data)
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        return redirect(url_for('home'))


@app.route('/generate-report', methods=['POST'])
def generate_report():
    try:
        print("⚙️ Received form input...")
        ai = request.form['ai']
        person_key = request.form['person']
        person = PERSONS[person_key]

        download_csv(person_key)

        print("🧼 Reading and cleaning CSV...")
        df = pd.read_csv("data.csv")
        df.columns = df.columns.str.strip()
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        df = df.dropna(subset=['Timestamp'])

        
        df = filter_last_n_days(df, LAST_N_DAYS)

        analysis = analyze_health_metrics(df)

        print("📨 Generating summary with AI...")
        prompt1 = f"""You are a health assistant. Analyze the health data for a {person['age']}-year-old {person['status']} individual.

Current metrics (calculated over the last {LAST_N_DAYS} days):
- Heart Rate: {analysis['heart_rate']['avg']} bpm (Status: {analysis['heart_rate']['status']})
- SpO₂: {analysis['spo2']['avg']}% (Status: {analysis['spo2']['status']})
- Blood Pressure: {analysis['blood_pressure']['systolic_avg']}/{analysis['blood_pressure']['diastolic_avg']} mmHg (Status: {analysis['blood_pressure']['status']})
- Overall Health Score: {analysis['health_score']}/100

Provide a detailed medical analysis including observations, potential concerns, and clinically sensible recommendations. Keep the tone supportive and non-alarming. Avoid diagnosing; focus on risk indicators and lifestyle guidance. """

        prompt2 = f"""Provide personalized health advice for {person['name']} ({person['age']} years old, {person['status']}).
Based on their health score of {analysis['health_score']}/100 (computed over the last {LAST_N_DAYS} days), give specific, actionable recommendations for:
1. Diet and nutrition
2. Exercise and activity
3. Lifestyle modifications
4. When to seek medical attention

Use supportive, encouraging language appropriate for their age and condition."""

        if ai == "openai":
            summary = generate_openai_summary(prompt1)
            tips = generate_openai_summary(prompt2)
        else:
            summary = generate_claude_summary(prompt1)
            tips = generate_claude_summary(prompt2)

        report_file = generate_pdf(person, summary, tips, analysis)
        send_email("📊 Monthly Health Report", f"Monthly report for {person['name']} attached. Health Score: {analysis['health_score']}/100", report_file)

        return redirect(url_for('dashboard', person_key=person_key))

    except Exception as err:
        print(f"🔥 Something failed: {err}")
        return "⚠️ Error occurred during report generation. Check logs."


if __name__ == '__main__':
    app.run(port=5003, host='0.0.0.0')
