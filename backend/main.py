from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import threading

from .database import engine, get_db
from .config import settings
from .models import Base, SensorReading
from .serial_reader import start_serial_listener, get_serial_status, list_serial_ports
from .llm_engine import ollama_generate, generate_explanation
from .shap_engine import explain_row
from .feature_engineering import FEATURE_BUFFER

app = FastAPI()

_serial_thread_started = False


@app.on_event("startup")
def startup_event():
    global _serial_thread_started

    # Create tables on startup (avoids import-time crash if env isn't ready yet).
    Base.metadata.create_all(bind=engine)

    if not _serial_thread_started:
        thread = threading.Thread(target=start_serial_listener, name="serial-listener", daemon=True)
        thread.start()
        _serial_thread_started = True
        print("[INFO] Serial listener started")


@app.get("/latest")
def get_latest(db: Session = Depends(get_db)):
    record = db.query(SensorReading).order_by(SensorReading.id.desc()).first()
    if not record:
        return {"status": "No data yet"}
    return {
        "id": record.id,
        "distance_cm": record.distance_cm,
        "rain_analog": record.rain_analog,
        "float_status": record.float_status,
        "predicted_risk": record.predicted_risk,
        "risk_probability": record.risk_probability,
        "explanation": record.explanation,
        "created_at": record.created_at,
    }


@app.get("/serial/status")
def serial_status():
    return get_serial_status()


@app.get("/serial/ports")
def serial_ports():
    return {"ports": list_serial_ports()}


@app.get("/llm/test")
def llm_test(prompt: str = "Reply with: OK"):
    # Simple endpoint to confirm Ollama is reachable.
    return {
        "model": settings.OLLAMA_MODEL,
        "response": ollama_generate(prompt),
    }


@app.get("/llm/explain/latest")
def llm_explain_latest(db: Session = Depends(get_db)):
    record = db.query(SensorReading).order_by(SensorReading.id.desc()).first()
    if not record:
        return {"status": "No data yet"}

    # Use stored risk/prob when available; otherwise fall back to placeholders.
    risk = record.predicted_risk if record.predicted_risk is not None else 0
    prob = record.risk_probability if record.risk_probability is not None else 0.0
    sensor_data = {
        "distance_cm": record.distance_cm,
        "rain_analog": record.rain_analog,
        "float_status": record.float_status,
    }
    return {
        "id": record.id,
        "explanation": generate_explanation(sensor_data, risk, prob),
    }


@app.get("/shap/explain/latest")
def shap_explain_latest(db: Session = Depends(get_db), top_k: int = 6):
    record = db.query(SensorReading).order_by(SensorReading.id.desc()).first()
    if not record:
        return {"status": "No data yet"}

    # Build a best-effort feature row using the latest raw reading.
    raw = {
        "distance_cm": record.distance_cm,
        "rain_analog": record.rain_analog,
        "float_status": record.float_status,
    }
    engineered = FEATURE_BUFFER.build_features(raw, update_state=False)
    exp = explain_row(engineered, top_k=top_k)
    return {
        "id": record.id,
        "predicted_class": exp.predicted_class,
        "predicted_label": exp.predicted_label,
        "probability": exp.probability,
        "top_features": exp.top_features,
    }
