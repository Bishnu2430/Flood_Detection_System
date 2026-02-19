from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import threading

from .database import engine, get_db
from .models import Base, SensorReading
from .serial_reader import start_serial_listener, get_serial_status, list_serial_ports

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
        "created_at": record.created_at,
    }


@app.get("/serial/status")
def serial_status():
    return get_serial_status()


@app.get("/serial/ports")
def serial_ports():
    return {"ports": list_serial_ports()}
