import logging

from .database import SessionLocal
from .models import SensorReading
from .ml_engine import predict_risk_safe
from .llm_engine import generate_explanation
from .validation import normalize_sensor_payload


logger = logging.getLogger("flood.processor")


def process_sensor_data(data: dict):

    # Local import to avoid circular import with serial_reader.
    from .serial_reader import send_alert

    db = SessionLocal()

    try:
        normalized = normalize_sensor_payload(data)
        payload = normalized.payload

        for w in normalized.warnings:
            logger.warning("payload_warning=%s raw=%s", w, data)

        # Safety override: if float switch is triggered, treat as high risk regardless of ML.
        emergency = payload.get("float_status") == 1

        # ML Prediction (non-fatal)
        risk = None
        prob = None
        err = None

        if emergency:
            risk, prob = 2, 1.0
            err = "emergency_override"
        elif normalized.errors:
            err = f"payload_errors={','.join(normalized.errors)}"
        else:
            risk, prob, err = predict_risk_safe(payload)

        if err and err != "emergency_override":
            logger.warning("ml_inference_skipped error=%s payload=%s", err, payload)

        # LLM reasoning + Arduino alert if high risk
        # Only run if risk is available.
        explanation = None
        if risk is not None and prob is not None:
            if risk >= 2:
                try:
                    explanation = generate_explanation(payload, risk, prob)
                except Exception as e:
                    logger.warning("llm_explanation_failed error=%s", e)
                send_alert("ALERT_ON")
            else:
                send_alert("ALERT_OFF")
        else:
            # If we cannot determine risk, prefer safe default (no alert)
            send_alert("ALERT_OFF")

        # Store in DB (always store raw)
        record = SensorReading(
            distance_cm=float(payload["distance_cm"]),
            rain_analog=int(payload["rain_analog"]),
            float_status=int(payload["float_status"]),
            predicted_risk=risk,
            risk_probability=prob,
            explanation=explanation,
        )

        db.add(record)
        db.commit()

        if risk is None:
            logger.info("stored_reading risk=n/a id=%s", record.id)
        else:
            logger.info("stored_reading risk=%s id=%s", risk, record.id)

    except Exception as e:
        logger.exception("processing_failed error=%s raw=%s", e, data)

    finally:
        db.close()
