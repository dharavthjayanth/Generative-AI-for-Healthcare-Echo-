# Generative-AI-for-Healthcare-Echo-

# 🩺 Echo – AI-Powered Health Consulting & Monitoring System
# 📖 Overview
Echo (part of the Intelligent Geriatric Care Management System – I-GCMS) is an AI-driven health assistant designed to support elderly care through:
Real-time health monitoring (via IoT + RabbitMQ).
AI-powered consultation (OpenAI GPT & Anthropic Claude).
Automated emergency alerts (voice + email).
Monthly personalized health reports (PDF with insights & charts).
The system is built with Flask, integrates with AWS S3 for dataset storage, and uses voice interaction for user confirmations.

# ⚙️ Features

# AI Consultation (Echo)

Switch between OpenAI GPT & Anthropic Claude.

Personalized responses for two profiles:
Person A: Healthy, 62 years old.
Person B: Frail, 92 years old.

Real-Time Health Monitoring
Vital signs (SpO2, Heart Rate, Blood Pressure) streamed every 2 minutes.
RabbitMQ sender/consumer architecture with sliding-window evaluation.
Automatic emergency detection & AI-generated alerts.

Voice prompt: “Are you okay?” → waits for response.
Emergency Alert System

If no response in 30s → Email alert with location & context.
If user responds → AI-generated health summary sent.

Monthly Reports
Fetch data from AWS S3.
Generate health trends & charts (Matplotlib).
AI-generated summaries & tips.
Export as PDF & send via email.

# 🏗️ System Architecture
IoT Device → RabbitMQ (Sender) → Flask Consumer → AI Model (GPT/Claude)
       ↓                                         ↓
   AWS S3 (CSV) ← Monthly Reports ← Flask ← User Interface (Web + Voice)

# 📊 Sample Dataset
Interval: Every 5 minutes
Metrics: Timestamp, SpO2, Heart Rate, BP_Sys, BP_Dia
Rows: ~8640 per month

# 🤝 Contributors

Dharavath Jayanth – Researcher & Developer
Asian Institute of Technology, Thailand
