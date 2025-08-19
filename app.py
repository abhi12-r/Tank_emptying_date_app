from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta, date
import math
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()  # loads .env file if present

# Config from environment (set these in your environment or a .env file)
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SHEET_NAME = os.getenv("SHEET_NAME", "TankEmptyingData")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "ce24m017@smail.iitm.ac.in")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # must be set in env or .env
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.iitm.ac.in")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Google Sheets scopes & client setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
# open sheet (create the sheet first in Google Drive)
try:
    sh = gc.open(SHEET_NAME)
    sheet = sh.sheet1
except Exception as e:
    # If sheet doesn't exist, try to create one (service account needs Drive permission)
    try:
        sh = gc.create(SHEET_NAME)
        sheet = sh.sheet1
        # set headers
        headers = ["timestamp", "email", "lat", "lon", "shape", "dimensions", "P", "q", "F", "S", "last_date", "next_emptying_date", "N_years"]
        sheet.append_row(headers)
    except Exception as e2:
        raise RuntimeError("Unable to open or create Google Sheet. Check service account permissions and sheet name.") from e2

app = Flask(__name__, static_folder='static', template_folder='templates')

def send_email(receiver_email, next_date_str, details=None):
    """
    Send an email (plain text) to receiver_email containing next emptying date.
    """
    if EMAIL_PASSWORD is None:
        print("EMAIL_PASSWORD not set in environment; skipping email send.")
        return False

    subject = "Tank Emptying Date"
    body_lines = [
        "Dear user,",
        "",
        f"Your next tank emptying date is: {next_date_str}",
        ""
    ]
    if details:
        body_lines.append("Details submitted:")
        for k, v in details.items():
            body_lines.append(f"{k}: {v}")
        body_lines.append("")

    body_lines.append("Regards,\nTeam")
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Failed to send email:", e)
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map')
def map_view():
    return render_template('map.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    try:
        # Inputs
        last_emptying_date = data.get('last_date')
        shape = data.get('shape')
        P = float(data.get('P'))  # Number of people
        q = float(data.get('q'))  # Sewage flow per person per day (L)
        F = float(data.get('F'))  # Digestion factor
        S = float(data.get('S'))  # Sludge accumulation rate (L/person/year)
        email = data.get('email', '').strip()
        lat = data.get('lat')
        lon = data.get('lon')

        # Dimensions based on shape
        dimensions_display = ""
        if shape == "rectangular":
            length = float(data.get('length'))
            width = float(data.get('width'))
            depth = float(data.get('depth'))
            volume_m3 = length * width * depth
            dimensions_display = f"L={length} m, W={width} m, D={depth} m"
        elif shape == "circular":
            diameter = float(data.get('diameter'))
            depth = float(data.get('depth'))
            radius = diameter / 2
            volume_m3 = math.pi * (radius ** 2) * depth
            dimensions_display = f"D={diameter} m, Depth={depth} m"
        else:
            return jsonify({"error": "Invalid shape"}), 400

        # Convert m³ to litres
        volume_litres = volume_m3 * 1000

        # WHO formula
        A = P * q  # Liquid retention (L)
        target_volume = (2 / 3) * volume_litres  # 2/3 full

        # Years until 2/3 full (N)
        # N = (V_target - A) / (P * F * S)
        denom = (P * F * S)
        if denom == 0:
            return jsonify({"error": "Invalid inputs lead to division by zero (check P, F, S)."}), 400

        N = (target_volume - A) / denom

        # If N is negative, next emptying is immediate/overdue; handle gracefully
        if N < 0:
            N_years = 0.0
            next_emptying_date = datetime.strptime(last_emptying_date, "%Y-%m-%d").date()
        else:
            N_years = N
            last_date_obj = datetime.strptime(last_emptying_date, "%Y-%m-%d").date()
            # N is in years (decimal). Convert to days
            days_to_add = int(N * 365)
            next_emptying_date = last_date_obj + timedelta(days=days_to_add)

        # Sludge & scum storage
        B = P * N_years * F * S

        # Check sum
        check_sum = A + B

        # Append to Google Sheet (timestamped)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp,
            email,
            lat if lat is not None else "",
            lon if lon is not None else "",
            shape,
            dimensions_display,
            P,
            q,
            F,
            S,
            last_emptying_date,
            next_emptying_date.strftime("%Y-%m-%d"),
            round(N_years, 3)
        ]
        try:
            sheet.append_row(row)
        except Exception as e:
            print("Warning: Failed to append to Google Sheet:", e)

        # send email
        details = {
            "shape": shape,
            "dimensions": dimensions_display,
            "P": P,
            "q": q,
            "F": F,
            "S": S
        }
        email_success = False
        if email:
            email_success = send_email(email, next_emptying_date.strftime("%Y-%m-%d"), details)

        response = {
            "volume_litres": round(volume_litres, 2),
            "target_volume": round(target_volume, 2),
            "A": round(A, 2),
            "B": round(B, 2),
            "check_sum": round(check_sum, 2),
            "N_years": round(N_years, 3),
            "next_emptying_date": next_emptying_date.strftime("%Y-%m-%d"),
            "email_sent": email_success
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/map-data', methods=['GET'])
def map_data():
    """
    Return all records from the sheet as JSON where lat/lon are present.
    Each record will include days_until (int).
    """
    try:
        records = sheet.get_all_records()
        out = []
        today = date.today()
        for rec in records:
            # expect rec has 'lat', 'lon', 'next_emptying_date' or matching header names
            lat = rec.get('lat') or rec.get('Lat') or rec.get('latitude') or rec.get('Latitude')
            lon = rec.get('lon') or rec.get('Lon') or rec.get('longitude') or rec.get('Longitude')
            next_date_str = rec.get('next_emptying_date') or rec.get('Next Emptying') or rec.get('next_emptying')
            email = rec.get('email') or rec.get('Email') or ""
            if not lat or not lon or not next_date_str:
                continue
            try:
                # ensure numeric lat/lon
                lat_f = float(lat)
                lon_f = float(lon)
                nd = datetime.strptime(next_date_str, "%Y-%m-%d").date()
                days_until = (nd - today).days
                out.append({
                    "email": email,
                    "lat": lat_f,
                    "lon": lon_f,
                    "next_emptying_date": next_date_str,
                    "days_until": days_until
                })
            except Exception:
                continue
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
