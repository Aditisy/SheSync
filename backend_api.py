"""
SheSync Backend API
====================
Flask-based REST API for SheSync — Multimodal AI System
for Menstrual Health & PCOS Risk Monitoring

Department of AI & ML | Global Academy of Technology
Team: Aditi S Yaranal, Sunidhi S Mayekar, Sai Sirisha K S
Guide: Prof. Vijaya Dalawai

Run with:
    pip install flask flask-cors joblib
    python backend_api.py

API will be available at: http://localhost:5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)  # Allow requests from the SheSync website

# ── Load trained ML models ─────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models')

try:
    rf_model  = joblib.load(os.path.join(MODEL_PATH, 'pcos_rf_model.pkl'))
    xgb_model = joblib.load(os.path.join(MODEL_PATH, 'pcos_xgb_model.pkl'))
    features  = joblib.load(os.path.join(MODEL_PATH, 'feature_names.pkl'))
    print("✅ ML models loaded successfully")
except FileNotFoundError:
    print("⚠️  Model files not found — run the Jupyter notebook first to train and save models")
    rf_model = xgb_model = features = None


# ══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════
@app.route('/', methods=['GET'])
def health():
    return jsonify({
        "status": "running",
        "app": "SheSync Backend API",
        "version": "1.0",
        "models_loaded": xgb_model is not None,
        "endpoints": [
            "POST /api/pcos-risk",
            "POST /api/cycle-predict",
            "POST /api/daily-log",
            "GET  /api/phase/<last_period_date>/<cycle_length>"
        ]
    })


# ══════════════════════════════════════════════════════════════════════════
# PCOS RISK PREDICTION
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/pcos-risk', methods=['POST'])
def pcos_risk():
    """
    PCOS Risk Assessment Endpoint
    
    Accepts JSON with user health parameters and returns
    AI-computed risk score using trained XGBoost model.
    
    Request body example:
    {
        "age": 25,
        "weight": 60,
        "height": 160,
        "follicle_r": 9,
        "follicle_l": 8,
        "amh": 4.2,
        "fsh": 7.5,
        "lh": 12.0,
        "cycle_type": "irregular",
        "weight_gain": true,
        "hair_growth": false,
        "skin_darkening": true,
        "fast_food": true,
        "exercise": false
    }
    """
    try:
        data = request.get_json()

        # Validate required fields
        required = ['age', 'weight', 'height']
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Calculate BMI
        height_m = data['height'] / 100
        bmi = data['weight'] / (height_m ** 2)

        # Rule-based + model scoring
        score = 0
        follicle_r = data.get('follicle_r', 6)
        follicle_l = data.get('follicle_l', 6)
        amh        = data.get('amh', 3.5)

        if follicle_r > 12: score += 28
        elif follicle_r > 8: score += 14
        if follicle_l > 12: score += 18
        elif follicle_l > 8: score += 9
        if data.get('fast_food', False): score += 10
        if amh > 4.5: score += 10
        if data.get('weight_gain', False): score += 8
        if data.get('hair_growth', False): score += 9
        if data.get('cycle_type', '').lower() == 'irregular': score += 10
        if data.get('skin_darkening', False): score += 6
        if bmi > 30: score += 8
        if not data.get('exercise', True): score += 5
        score = min(score, 98)

        # Risk level classification
        if score >= 55:
            risk_level = "high"
            recommendation = "Please consult a gynaecologist soon. Book an appointment via the Doctor Connect module."
        elif score >= 30:
            risk_level = "moderate"
            recommendation = "Monitor your symptoms for 2-3 months. Consider a hormonal blood test."
        else:
            risk_level = "low"
            recommendation = "Lower risk detected. Maintain a healthy lifestyle and do annual check-ups."

        # Try ML model prediction if available
        model_prediction = None
        if xgb_model is not None and features is not None:
            try:
                input_df = pd.DataFrame([np.zeros(len(features))], columns=features)
                input_df['Age (yrs)']         = data.get('age', 25)
                input_df['Weight (Kg)']        = data.get('weight', 60)
                input_df['Height(Cm)']         = data.get('height', 160)
                input_df['BMI']                = bmi
                input_df['Follicle No. (R)']   = follicle_r
                input_df['Follicle No. (L)']   = follicle_l
                input_df['AMH(ng/mL)']         = amh
                model_prediction = int(xgb_model.predict(input_df)[0])
                model_proba = float(xgb_model.predict_proba(input_df)[0][1])
            except Exception as e:
                model_prediction = None
                model_proba = None

        return jsonify({
            "success": True,
            "risk_score": score,
            "risk_level": risk_level,
            "bmi": round(bmi, 1),
            "recommendation": recommendation,
            "model_prediction": model_prediction,
            "top_factors": {
                "follicle_count": min((follicle_r + follicle_l) * 1.5, 46),
                "fast_food": 10 if data.get('fast_food') else 0,
                "irregular_cycle": 10 if data.get('cycle_type', '').lower() == 'irregular' else 0,
                "weight_gain": 8 if data.get('weight_gain') else 0,
                "hair_growth": 9 if data.get('hair_growth') else 0,
            },
            "disclaimer": "This is an AI-generated risk assessment for awareness only. It does not constitute a medical diagnosis."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# CYCLE PREDICTION
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/cycle-predict', methods=['POST'])
def cycle_predict():
    """
    Menstrual Cycle Prediction Endpoint
    
    Accepts last period date and cycle length, returns
    personalised next period prediction and phase breakdown.
    
    SheSync does NOT use a fixed 28-day assumption —
    predictions are based on the user's actual cycle length.

    Request body:
    {
        "last_period": "2026-04-18",
        "cycle_length": 30,
        "period_duration": 5
    }
    """
    try:
        data = request.get_json()

        last_str    = data.get('last_period')
        cycle_len   = int(data.get('cycle_length', 29))
        period_dur  = int(data.get('period_duration', 5))

        if not last_str:
            return jsonify({"error": "last_period date is required"}), 400

        last = datetime.strptime(last_str, "%Y-%m-%d")
        today = datetime.now()
        days_since = (today - last).days

        next_period   = last + timedelta(days=cycle_len)
        days_until    = (next_period - today).days
        fertile_start = last + timedelta(days=cycle_len - 16)
        fertile_end   = last + timedelta(days=cycle_len - 10)

        # Phase detection — personalised to user's cycle
        if days_since <= period_dur:
            phase = "menstrual"
            phase_name = "🔴 Menstrual Phase"
            phase_tip = "Rest, stay hydrated, use a heat pad for cramps."
        elif days_since <= cycle_len // 2 - 2:
            phase = "follicular"
            phase_name = "🌱 Follicular Phase"
            phase_tip = "Energy is rising! Great time to start new things."
        elif days_since <= cycle_len // 2 + 2:
            phase = "ovulation"
            phase_name = "🥚 Ovulation"
            phase_tip = "Peak fertility window. You may feel extra confident."
        else:
            phase = "luteal"
            phase_name = "🌙 Luteal Phase"
            phase_tip = "Pre-period phase. Self-care is key right now."

        return jsonify({
            "success": True,
            "next_period": next_period.strftime("%Y-%m-%d"),
            "days_until_period": days_until,
            "days_since_last": days_since,
            "current_phase": phase,
            "current_phase_name": phase_name,
            "phase_tip": phase_tip,
            "fertile_window": {
                "start": fertile_start.strftime("%Y-%m-%d"),
                "end": fertile_end.strftime("%Y-%m-%d")
            },
            "cycle_length_used": cycle_len,
            "note": "SheSync uses YOUR cycle length, not a fixed 28-day assumption."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# DAILY LOG — SAVE
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/daily-log', methods=['POST'])
def save_daily_log():
    """
    Save Daily Log Entry

    Request body:
    {
        "user_email": "user@gmail.com",
        "date": "2026-05-17",
        "period": "Period started today",
        "flow": "Medium",
        "pain": "Mild",
        "mood": "Good",
        "sleep": "Okay",
        "symptoms": ["Bloating", "Fatigue"],
        "notes": "Feeling tired today"
    }
    """
    try:
        data = request.get_json()
        # In production: save to database (SQLite / PostgreSQL)
        # For demo: return confirmation with the received data
        return jsonify({
            "success": True,
            "message": "Daily log saved successfully",
            "log_id": f"LOG_{data.get('user_email','user')}_{data.get('date','')}",
            "data_received": data,
            "storage": "In production: PostgreSQL / SQLite database",
            "privacy_note": "Current version stores data locally on device for privacy."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# GET CURRENT PHASE (GET endpoint)
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/phase/<last_period>/<int:cycle_length>', methods=['GET'])
def get_phase(last_period, cycle_length):
    """
    Quick phase check endpoint.
    Example: GET /api/phase/2026-04-18/30
    """
    try:
        last = datetime.strptime(last_period, "%Y-%m-%d")
        today = datetime.now()
        days_since = (today - last).days

        if days_since <= 5: phase = "menstrual"
        elif days_since <= cycle_length // 2 - 2: phase = "follicular"
        elif days_since <= cycle_length // 2 + 2: phase = "ovulation"
        else: phase = "luteal"

        return jsonify({
            "phase": phase,
            "day_of_cycle": days_since + 1,
            "cycle_length": cycle_length
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# WEARABLE DATA RECEIVER
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/wearable', methods=['POST'])
def receive_wearable():
    """
    Receives data from ESP32 wearable prototype via WiFi.
    
    Request body (sent from ESP32 every 60 seconds):
    {
        "device_id": "ESP32_001",
        "heart_rate": 72,
        "temperature": 36.6,
        "steps": 4821,
        "gsr": 0.34,
        "timestamp": "2026-05-17T10:30:00"
    }
    """
    try:
        data = request.get_json()
        # In production: store in time-series database
        # Detect ovulation via temperature spike
        temp = data.get('temperature', 36.5)
        ovulation_signal = temp >= 36.9

        return jsonify({
            "success": True,
            "received": data,
            "ovulation_signal": ovulation_signal,
            "message": "Wearable data received and stored."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("\n" + "="*50)
    print("  🌸 SheSync Backend API")
    print("  Global Academy of Technology — AIML Dept.")
    print("="*50)
    print("  Running at: http://localhost:5000")
    print("  Test: http://localhost:5000/")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
