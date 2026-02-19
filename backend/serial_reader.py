from __future__ import annotations

import json
import time
import threading
from typing import Any, Dict, List, Optional

import serial
from serial.tools import list_ports

from .config import settings
from .processor import process_sensor_data


_ser: Optional[serial.Serial] = None
_lock = threading.Lock()

_status: Dict[str, Any] = {
    "connected": False,
    "port": None,
    "baudrate": settings.SERIAL_BAUDRATE,
    "last_line": None,
    "last_json": None,
    "last_error": None,
    "last_connected_at": None,
}


def list_serial_ports() -> List[Dict[str, str]]:
    ports = []
    for p in list_ports.comports():
        ports.append(
            {
                "device": p.device,
                "description": p.description or "",
                "manufacturer": getattr(p, "manufacturer", "") or "",
                "hwid": p.hwid or "",
            }
        )
    return ports


def _auto_detect_port() -> Optional[str]:
    # Prefer ports that look like Arduino/USB-serial.
    candidates = list_ports.comports()
    if not candidates:
        return None

    def score(p) -> int:
        text = " ".join(
            [
                p.device or "",
                p.description or "",
                getattr(p, "manufacturer", "") or "",
                p.hwid or "",
            ]
        ).lower()
        keywords = ["arduino", "usb serial", "wch", "ch340", "cp210", "ftdi", "silicon labs"]
        return sum(1 for k in keywords if k in text)

    best = max(candidates, key=score)
    return best.device


def get_serial_status() -> Dict[str, Any]:
    with _lock:
        return dict(_status)


def _set_status(**kwargs: Any) -> None:
    with _lock:
        _status.update(kwargs)


def _connect(port: str) -> Optional[serial.Serial]:
    global _ser
    try:
        # DTR toggle helps reset some Arduino boards so they start sending immediately.
        ser = serial.Serial(port, settings.SERIAL_BAUDRATE, timeout=1)
        try:
            ser.setDTR(False)
            time.sleep(0.2)
            ser.reset_input_buffer()
            ser.setDTR(True)
        except Exception:
            # Not all adapters support all control lines; ignore.
            pass

        _ser = ser
        _set_status(
            connected=True,
            port=port,
            baudrate=settings.SERIAL_BAUDRATE,
            last_error=None,
            last_connected_at=time.time(),
        )
        print(f"[INFO] Connected to {port} @ {settings.SERIAL_BAUDRATE}")
        return ser
    except Exception as e:
        _ser = None
        _set_status(connected=False, port=port, last_error=str(e))
        print(f"[ERROR] Serial connection failed ({port}): {e}")
        return None


def get_serial_connection() -> Optional[serial.Serial]:
    global _ser
    if _ser is not None and _ser.is_open:
        return _ser

    port = settings.SERIAL_PORT
    if not port:
        port = _auto_detect_port()
        if port:
            print(f"[INFO] Auto-detected serial port: {port}")
        else:
            _set_status(connected=False, port=None, last_error="No serial ports detected")
            return None

    return _connect(port)


def start_serial_listener() -> None:
    print("[INFO] Serial listener starting...")
    while True:
        connection = get_serial_connection()
        if not connection:
            time.sleep(settings.SERIAL_CONNECT_RETRY_SECONDS)
            continue

        print("[INFO] Listening for sensor data...")
        try:
            while True:
                raw = connection.readline()
                if not raw:
                    continue

                line = raw.decode(errors="replace").strip()
                _set_status(last_line=line)

                if not (line.startswith("{") and line.endswith("}")):
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                _set_status(last_json=data)
                process_sensor_data(data)

        except Exception as e:
            _set_status(connected=False, last_error=str(e))
            print(f"[ERROR] Serial read loop failed: {e}")
            try:
                connection.close()
            except Exception:
                pass
            _ser = None
            time.sleep(settings.SERIAL_CONNECT_RETRY_SECONDS)


def send_alert(command: str) -> None:
    connection = get_serial_connection()
    if not connection:
        return

    try:
        connection.write((command + "\n").encode())
    except Exception as e:
        _set_status(last_error=str(e))
        print(f"[ERROR] Serial write failed: {e}")
