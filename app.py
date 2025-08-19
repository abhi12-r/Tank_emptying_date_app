from flask import Flask, request, jsonify, render_template
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os   # <-- new for environment variables

app = Flask(__name__)

# Your Google Apps Script Web App endpoint
GOOGLE_SHEET_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyqb7rO2tTM1bumy2GoRFXuz22Ssl522zeLR8cc3VKQadbrqGD9EI-PUv-9dWtQk1fzCA/exec"

# Mail settings (now from environment variables in Render dashboard)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASS")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    # Extract inputs
    email = data.get("email")
    lat = data.get("lat")
    lon = data.get("lon")
    shape = data.get("shape")
    volume = float(data.get("volume_litres"))
    P = float(data.get("P"))
    q = float(data.get("q"))
    F = float(data.get("F"))
    S = float(data.get("S"))
    N = float(data.get("N_years"))

    # Emptying time calculation
    T_days = (volume - (P * S)) / (P * (q + F / 365))
    emptying_date = datetime.now() + timedelta(days=T_days)
    next_emptying_date = emptying_date.strftime("%Y-%m-%d")

    # Send data to Google Sheet
    sheet_payload = {
        "email": email,
        "lat": lat,
        "lon": lon,
        "shape": shape,
        "volume_litres": volume,
        "P": P,
        "q": q,
        "F": F,
        "S": S,
        "N_years": N,
        "next_emptying_date": next_emptying_date
    }
    try:
        requests.post(GOOGLE_SHEET_WEBAPP_URL, data=sheet_payload)
    except Exception as e:
        print("Error updating Google Sheet:", e)

    # Send confirmation email
    try:
        msg = MIMEText(
            f"Hello,\n\nYour septic tank needs emptying on: {next_emptying_date}.\n\nLocation: ({lat}, {lon})"
        )
        msg["Subject"] = "Septic Tank Emptying Date"
        msg["From"] = SENDER_EMAIL
        msg["To"] = email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [email], msg.as_string())
    except Exception as e:
        print("Error sending email:", e)

    # Return response
    return jsonify({"next_emptying_date": next_emptying_date})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
