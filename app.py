from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json

    # Inputs with labels
    last_emptying_date = data.get('last_date')  # YYYY-MM-DD
    P = float(data.get('P'))  # Number of people using the pit latrine
    q = float(data.get('q'))  # Sewage flow per person per day (litres)
    F = float(data.get('F'))  # Digestion factor
    S = float(data.get('S'))  # Sludge accumulation rate (litres/person/year)
    shape = data.get('shape')

    # Volume calculation
    if shape == "rectangular":
        length = float(data.get('length'))
        width = float(data.get('width'))
        depth = float(data.get('depth'))
        volume_m3 = length * width * depth

    elif shape == "circular":
        diameter = float(data.get('diameter'))
        depth = float(data.get('depth'))
        radius = diameter / 2
        volume_m3 = 3.1416 * (radius ** 2) * depth

    else:
        return jsonify({"error": "Invalid shape"}), 400

    # Convert to litres
    volume_litres = volume_m3 * 1000

    # WHO formulas
    A = P * q  # Volume for 24 hrs retention
    target_volume = (2/3) * volume_litres  # 2/3 of tank volume

    # Years until 2/3 full
    N = (target_volume - A) / (P * F * S)

    # Next emptying date
    last_date_obj = datetime.strptime(last_emptying_date, "%Y-%m-%d")
    next_emptying_date = last_date_obj + timedelta(days=N * 365)

    return jsonify({
        "volume_litres": round(volume_litres, 2),
        "target_volume": round(target_volume, 2),
        "A": round(A, 2),
        "N_years": round(N, 2),
        "next_emptying_date": next_emptying_date.strftime("%Y-%m-%d")
    })

if __name__ == '__main__':
    app.run(debug=True)
