from .database import SessionLocal
from .models import SensorReading
from .ml_engine import predict_risk_safe
from .llm_engine import generate_explanation


def process_sensor_data(data: dict):

    # Local import to avoid circular import with serial_reader.
    from .serial_reader import send_alert

    db = SessionLocal()

    try:
        # ML Prediction (non-fatal)
        risk, prob, err = predict_risk_safe(data)
        if err:
            print(f"[WARN] ML inference skipped: {err}")

        # LLM reasoning + Arduino alert if high risk
        # Only run if risk is available.
        if risk is not None and prob is not None:
            if risk >= 2:
                _ = generate_explanation(data, risk, prob)
                send_alert("ALERT_ON")
            else:
                send_alert("ALERT_OFF")

        # Store in DB (always store raw)
        record = SensorReading(
            distance_cm=float(data["distance_cm"]),
            rain_analog=int(data["rain_analog"]),
            float_status=int(data["float_status"]),
            predicted_risk=risk,
            risk_probability=prob,
        )

        db.add(record)
        db.commit()

        if risk is None:
            print("[INFO] Stored reading | Risk: (n/a)")
        else:
            print(f"[INFO] Stored reading | Risk: {risk}")

    except Exception as e:
        print(f"[ERROR] Processing failed: {e}")

    finally:
        db.close()
