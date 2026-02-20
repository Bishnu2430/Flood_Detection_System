# Flood Detection System — Current State (as implemented)

Date: 2026-02-20

## 1) What works end-to-end

This repo currently supports an end-to-end pipeline:

1. Arduino emits newline-delimited JSON over USB serial (COM port).
2. FastAPI backend reads the serial stream in a background thread.
3. Backend computes engineered features and runs the trained ML model.
4. Backend stores raw + ML outputs into PostgreSQL.
5. If risk is high (>= 2), backend requests an LLM explanation from Ollama and stores it.
6. Backend sends an `ALERT_ON` / `ALERT_OFF` command back to Arduino over serial.

Additionally:

- A React dashboard in `frontend/` visualizes latest readings, trends, SHAP explainability, and live LLM streaming output.

## 2) Repo structure

- `backend/`: FastAPI service + ML/LLM/SHAP logic
- `ml/`: training notebook + datasets + exported model artifacts
- `sketch_feb19a/`: Arduino sketch
- `docker-compose.yml`: Postgres + Ollama services
- `.env`: runtime configuration

## 3) Runtime components

### A. Backend API (FastAPI)

Entry point:

- `backend/main.py` (starts a daemon serial listener on startup)

Key behaviors:

- Starts serial reader once on application startup.
- Writes to Postgres using SQLAlchemy.
- Does not provide a UI; root `/` will 404 unless you add a route.

### B. Serial ingestion

Implemented in:

- `backend/serial_reader.py`

Features:

- Auto-detects a likely Arduino/USB-serial port if `SERIAL_PORT` is not set.
- Reconnect loop with backoff.
- Tracks status (`/serial/status`) including last line and last parsed JSON.

Expected Arduino JSON per line:

```json
{ "distance_cm": 123.4, "rain_analog": 512, "float_status": 0 }
```

### C. Processing pipeline

Implemented in:

- `backend/processor.py`

Steps:

- Runs ML prediction (non-fatal if it fails).
- If risk/probability are available:
  - risk >= 2: attempts LLM explanation and sends `ALERT_ON`
  - else: sends `ALERT_OFF`
- Always stores raw sensor data even if ML/LLM fails.

### D. ML inference

Implemented in:

- `backend/ml_engine.py`

Model artifacts:

- `ml/Model/flood_model.pkl`
- `ml/Model/flood_model_meta.pkl` (contains expected feature list and label map)

Important detail:

- The model expects engineered features. The backend uses an in-memory rolling buffer (`backend/feature_engineering.py`) to compute them.
- Feature buffer state resets on backend restart.

Dependency compatibility:

- The exported model was created with `scikit-learn==1.6.1`. The backend pins `scikit-learn==1.6.1` to avoid `InconsistentVersionWarning` during unpickle.

### E. LLM explanations (Ollama)

Implemented in:

- `backend/llm_engine.py`

Docker container:

- `flood_ollama` on port `11434`

Notes:

- Cold-start model load can take ~20s+; timeout is configurable via `OLLAMA_TIMEOUT_SECONDS`.
- The backend uses Ollama’s `/api/generate` endpoint.

### F. SHAP explainability

Implemented in:

- `backend/shap_engine.py` and endpoint in `backend/main.py`

Notes:

- The SHAP endpoint computes engineered features for the latest reading without mutating the online feature buffer state.

## 4) Database

Docker container:

- `flood_postgres` exposed on host port `5433`

ORM model:

- `backend/models.py`

Table: `sensor_readings`

- `id` (pk)
- `distance_cm` (float)
- `rain_analog` (int)
- `float_status` (int)
- `predicted_risk` (int, nullable)
- `risk_probability` (float, nullable)
- `explanation` (text, nullable)
- `created_at` (timestamp w/ tz, default now)

Connect via psql (local dev):

- `psql -h 127.0.0.1 -p 5433 -U flood -d flooddb`

## 5) API endpoints (current)

- `GET /latest`
  - returns latest DB record (raw + ML outputs + stored LLM explanation)
- `GET /serial/status`
  - connection + last line + last JSON
- `GET /serial/ports`
  - lists available serial ports
- `GET /llm/test?prompt=...`
  - sanity-check Ollama connectivity
- `GET /llm/explain/stream/latest`
  - streams a live explanation for the latest record using Server-Sent Events (SSE)
  - emits events: `meta`, `ml_perf`, repeated `token`, then `done`
- `GET /ml/predict/latest`
  - best-effort ML timing + prediction for the latest reading
- `GET /shap/explain/latest?top_k=6`
  - returns top SHAP feature contributions for the latest reading
  - SHAP direction is defined against a risk target class (typically the highest severity label)

## 6) Configuration (.env)

The backend loads `.env` from the repo root.

Common keys:

- Postgres:
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
  - optional `DATABASE_URL` override
- Serial:
  - `SERIAL_PORT` (optional; auto-detect if unset)
  - `SERIAL_BAUDRATE` (default 9600)
  - `SERIAL_CONNECT_RETRY_SECONDS` (default 2)
- Ollama:
  - `OLLAMA_URL` (default `http://localhost:11434/api/generate`)
  - `OLLAMA_MODEL` (e.g. `phi3:mini`)
  - `OLLAMA_TIMEOUT_SECONDS` (default 60)

## 7) How to run (local dev)

1. Start infra:
   - `docker compose up -d`
2. Install backend deps into the existing repo venv:

- `./venv/Scripts/python.exe -m pip install -r backend/requirements.txt`

3. Run backend using that venv:

- `./venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload`

4. Run the dashboard:

- `cd frontend && npm install && npm run dev`

## 8) Known limitations / gaps

- Serial may be disconnected in dev (COM port not present). Use readiness checks with `require_serial=false`.
- No external notification service is implemented (only serial `ALERT_ON/OFF`).
- Engineered features use an in-memory buffer; restarting the backend resets rolling/trend features.
- Arduino may emit `distance_cm = -1` on invalid ultrasonic reads; the backend currently stores it as-is.
- Root `/` returns 404 (expected unless a health/root route is added).
