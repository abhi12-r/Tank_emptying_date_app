from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import math

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

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

        # Dimensions based on shape
        if shape == "rectangular":
            length = float(data.get('length'))
            width = float(data.get('width'))
            depth = float(data.get('depth'))
            volume_m3 = length * width * depth

        elif shape == "circular":
            diameter = float(data.get('diameter'))
            depth = float(data.get('depth'))  # from circular input
            radius = diameter / 2
            volume_m3 = math.pi * (radius ** 2) * depth

        else:
            return jsonify({"error": "Invalid shape"}), 400

        # Convert m³ to litres
        volume_litres = volume_m3 * 1000

        # WHO formula
        A = P * q  # Liquid retention (L)
        target_volume = (2 / 3) * volume_litres  # 2/3 full

        # Years until 2/3 full
        N = (target_volume - A) / (P * F * S)

        # Sludge & scum storage
        B = P * N * F * S

        # Check sum
        check_sum = A + B

        # Next emptying date
        last_date_obj = datetime.strptime(last_emptying_date, "%Y-%m-%d")
        next_emptying_date = last_date_obj + timedelta(days=N * 365)

        return jsonify({
            "volume_litres": round(volume_litres, 2),
            "target_volume": round(target_volume, 2),
            "A": round(A, 2),
            "B": round(B, 2),
            "check_sum": round(check_sum, 2),
            "N_years": round(N, 2),
            "next_emptying_date": next_emptying_date.strftime("%Y-%m-%d")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
