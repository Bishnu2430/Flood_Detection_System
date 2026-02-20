from contextlib import asynccontextmanager
import logging
import json
import time

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import threading
from sqlalchemy import text

from .database import engine, get_db
from .config import settings
from .models import Base, SensorReading
from .serial_reader import start_serial_listener, stop_serial_listener, get_serial_status, list_serial_ports
from .llm_engine import ollama_generate, generate_explanation, ollama_is_available, ollama_stream
from .shap_engine import explain_row
from .feature_engineering import FEATURE_BUFFER
from .logging_config import configure_logging
from .validation import normalize_sensor_payload
from .ml_engine import predict_risk_safe_no_state

logger = logging.getLogger("flood.api")

_serial_thread: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _serial_thread

    configure_logging()
    logger.info("app_starting")

    # Create tables on startup (avoids import-time crash if env isn't ready yet).
    Base.metadata.create_all(bind=engine)

    if _serial_thread is None or not _serial_thread.is_alive():
        _serial_thread = threading.Thread(target=start_serial_listener, name="serial-listener", daemon=True)
        _serial_thread.start()
        logger.info("serial_listener_started")

    try:
        yield
    finally:
        logger.info("app_stopping")
        stop_serial_listener()
        if _serial_thread is not None:
            _serial_thread.join(timeout=3)
        logger.info("app_stopped")


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(require_serial: bool = True, include_llm: bool = False):
    # DB check
    db_ok = False
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_error = str(e)

    serial = get_serial_status()
    serial_ok = bool(serial.get("connected"))

    llm_ok = None
    llm_error = None
    if include_llm:
        llm_ok, llm_error = ollama_is_available()

    is_ready = db_ok and (serial_ok if require_serial else True) and (llm_ok if include_llm else True)
    payload = {
        "ready": is_ready,
        "db": {"ok": db_ok, "error": db_error},
        "serial": {"ok": serial_ok, "port": serial.get("port"), "error": serial.get("last_error")},
    }
    if include_llm:
        payload["llm"] = {"ok": bool(llm_ok), "error": llm_error, "model": settings.OLLAMA_MODEL}

    if not is_ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload


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


@app.get("/readings")
def get_readings(limit: int = 200, db: Session = Depends(get_db)):
    limit = max(1, min(int(limit), 5000))
    rows = (
        db.query(SensorReading)
        .order_by(SensorReading.id.desc())
        .limit(limit)
        .all()
    )

    # Return oldest->newest for charting.
    rows.reverse()
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "distance_cm": r.distance_cm,
                "rain_analog": r.rain_analog,
                "float_status": r.float_status,
                "predicted_risk": r.predicted_risk,
                "risk_probability": r.risk_probability,
                "created_at": r.created_at,
            }
            for r in rows
        ],
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


@app.get("/ml/predict/latest")
def ml_predict_latest(db: Session = Depends(get_db)):
    record = db.query(SensorReading).order_by(SensorReading.id.desc()).first()
    if not record:
        return {"status": "No data yet"}

    raw = {
        "distance_cm": record.distance_cm,
        "rain_analog": record.rain_analog,
        "float_status": record.float_status,
    }

    normalized = normalize_sensor_payload(raw)
    if normalized.errors:
        return {
            "id": record.id,
            "ok": False,
            "error": "payload_not_predictable",
            "errors": normalized.errors,
        }

    t0 = time.perf_counter()
    risk, prob, err = predict_risk_safe_no_state(normalized.payload)
    ms = int((time.perf_counter() - t0) * 1000)

    return {
        "id": record.id,
        "ok": err is None,
        "predicted_risk": risk,
        "risk_probability": prob,
        "error": err,
        "inference_ms": ms,
    }


@app.get("/llm/explain/stream/latest")
def llm_explain_stream_latest(db: Session = Depends(get_db)):
    record = db.query(SensorReading).order_by(SensorReading.id.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail={"error": "no_data"})

    # Use stored prediction when available, otherwise fall back to safe defaults.
    risk = record.predicted_risk if record.predicted_risk is not None else 0
    prob = record.risk_probability if record.risk_probability is not None else 0.0
    sensor_data = {
        "distance_cm": record.distance_cm,
        "rain_analog": record.rain_analog,
        "float_status": record.float_status,
    }

    prompt = f"""
You are a Flood Risk Intelligence Agent.

Current Sensor Data:
Water Height/Distance: {sensor_data.get('distance_cm')} cm
Rain Level: {sensor_data.get('rain_analog')}
Float Triggered: {sensor_data.get('float_status')}

Predicted Risk Level: {risk}
Probability: {prob:.2f}

Explain the flood risk clearly and recommend safety actions.
"""

    # Also compute ML perf without mutating state.
    normalized = normalize_sensor_payload(sensor_data)
    ml_payload = {"ok": False}
    if not normalized.errors:
        t0 = time.perf_counter()
        mr, mp, me = predict_risk_safe_no_state(normalized.payload)
        ml_payload = {
            "ok": me is None,
            "predicted_risk": mr,
            "risk_probability": mp,
            "error": me,
            "inference_ms": int((time.perf_counter() - t0) * 1000),
        }
    else:
        ml_payload = {
            "ok": False,
            "error": "payload_not_predictable",
            "errors": normalized.errors,
        }

    def sse(event: str, data_obj) -> str:
        return f"event: {event}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"

    def gen():
        yield sse(
            "meta",
            {
                "id": record.id,
                "model": settings.OLLAMA_MODEL,
                "created_at": str(record.created_at),
                "sensor": sensor_data,
                "stored_prediction": {"risk": risk, "probability": prob},
            },
        )
        yield sse("ml_perf", ml_payload)

        token_count = 0
        for chunk, final_stats in ollama_stream(prompt):
            if chunk:
                token_count += 1
                yield sse("token", {"text": chunk})
            if final_stats is not None:
                final_stats["token_events"] = token_count
                yield sse("done", final_stats)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/shap/explain/latest")
def shap_explain_latest(db: Session = Depends(get_db), top_k: int = 6):
    record = db.query(SensorReading).order_by(SensorReading.id.desc()).first()
    if not record:
        return {"status": "No data yet"}

    # Build a best-effort feature row using the latest raw reading.
    raw = {"distance_cm": record.distance_cm, "rain_analog": record.rain_analog, "float_status": record.float_status}
    normalized = normalize_sensor_payload(raw)
    if normalized.errors:
        raise HTTPException(status_code=422, detail={"error": "latest_sample_not_explainable", "errors": normalized.errors})

    engineered = FEATURE_BUFFER.build_features(normalized.payload, update_state=False)
    try:
        exp = explain_row(engineered, top_k=top_k, target="risk")
    except ModuleNotFoundError as e:
        # SHAP is an optional dependency during development.
        raise HTTPException(
            status_code=503,
            detail={
                "error": "shap_unavailable",
                "message": "SHAP is not installed in the backend environment.",
                "missing": str(e),
            },
        )
    return {
        "id": record.id,
        "predicted_class": exp.predicted_class,
        "predicted_label": exp.predicted_label,
        "probability": exp.probability,
        "target_class": exp.target_class,
        "target_label": exp.target_label,
        "target_probability": exp.target_probability,
        "top_features": exp.top_features,
    }
