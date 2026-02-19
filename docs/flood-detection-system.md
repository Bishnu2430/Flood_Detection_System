# Flood Detection System — Overview

## 1) Purpose

The Flood Detection System is a real-time, sensor-driven pipeline that:

- Collects live water/rain/emergency signals from an IoT sensor node (Arduino).
- Converts the raw stream into a feature vector suitable for the trained ML model.
- Produces a flood **risk level** and **probability**.
- Optionally generates a human-readable explanation (agentic reasoning) and triggers a safety response.
- Stores readings and decisions for monitoring and audit.

## 2) Architecture (Conceptual)

This project follows the same logical structure shown in the architecture diagrams:

### A. Data Ingestion Hub

**Live Sensors (IoT Stream) → Sensor Repository**

- **Live Sensors**: Ultrasonic distance sensor (water distance/height proxy), rain sensor (analog), float switch (binary emergency indicator).
- **Acquisition/Formatting**: Arduino samples sensors and emits newline-delimited JSON over USB serial.
- **Repository**: A PostgreSQL database stores the time series of readings and the intelligence outputs.

### B. Intelligence Core

**Feature Engine Vectorization → ML Risk Model → Agentic Reasoning**

- **Feature Engine Vectorization**: Converts raw sensor fields into engineered features expected by the trained model (rolling stats, trends, time features).
- **ML Risk Model**: A trained classifier predicts a discrete risk class plus an associated probability.
- **Context Injection**: The ML outputs and latest sensor context can be injected into an LLM prompt for explanation.
- **Decision Logging**: Inputs and outputs are persisted for traceability.

### C. Response Layer

**Explainable Risk Output → Safety Protocol**

- The system produces a user-facing explanation of the risk and recommended actions.
- A safety protocol can trigger:
  - Local alerts (e.g., buzzer/LED on Arduino)
  - External notifications (SMS/email/push)
  - Dashboard visualization

## 3) Hardware + Sensor Model

### Sensor Node

The Arduino node is responsible for:

- Sampling sensors on a fixed interval.
- Detecting emergency states (float switch).
- Emitting a compact JSON record over serial.

### Data Contract (Serial JSON)

Each sensor reading is emitted as a single JSON object per line:

```json
{ "distance_cm": 123.4, "rain_analog": 512, "float_status": 0 }
```

Field meanings:

- `distance_cm` (float): Ultrasonic distance reading (cm). If the sensor fails, the sketch may output `-1`.
- `rain_analog` (int): Raw ADC reading (typically 0–1023).
- `float_status` (int): 1 if triggered, else 0.

## 4) Backend Service Responsibilities

The backend (FastAPI) is the system hub that:

- Connects to the Arduino serial port (explicit port or auto-detected).
- Parses JSON safely from the serial stream.
- Runs the intelligence pipeline:
  - feature engineering
  - ML inference
  - optional LLM explanation
- Stores the resulting record in PostgreSQL.
- Provides HTTP endpoints to retrieve the latest state, serial health, and explanation outputs.

## 5) ML Risk Model

### Output

The risk model produces:

- `predicted_risk` (int): discrete class (e.g., Safe/Warning/Critical).
- `risk_probability` (float): probability associated with the predicted class.

### Feature Engineering Requirement

The trained model expects engineered features beyond raw sensor values.
A rolling window buffer is used to compute features such as:

- rolling mean/std of distance
- short-term rain trend
- rise rate (derived from distance changes)
- cumulative rain approximation
- time-based features (hour/day/month/season)

This implies:

- The model output depends on the recent history in memory.
- After a backend restart, engineered features “warm up” again from fresh samples.

## 6) Agentic Reasoning (LLM)

An LLM can generate a plain-language explanation using:

- current sensor values
- predicted risk and probability

Key design points:

- The system must tolerate the LLM being unavailable (timeouts, missing models, network issues).
- Explanations should be logged for audit.
- Cold-start latency is expected for local models; timeouts must be tuned accordingly.

## 7) Explainability (SHAP)

SHAP provides feature-attribution for the ML prediction:

- Explains which engineered features contributed most to the predicted class.
- Returns ranked contributions with direction (increasing vs decreasing risk).

## 8) Storage + Monitoring

### Sensor Repository (PostgreSQL)

Stores:

- raw sensor readings
- ML outputs
- optional LLM explanation
- timestamps

This supports:

- monitoring dashboards
- forensic review after incidents
- model evaluation against historical events

## 9) Deployment Topology (Local Dev)

- **PostgreSQL** runs in Docker.
- **Ollama (LLM runtime)** runs in Docker with a persistent model volume.
- **FastAPI backend** runs locally (Python venv) and connects to both.

## 10) Future Extensions (Concept-level)

Depending on project goals, the response layer can be extended with:

- A web monitoring dashboard (charts, latest status, explanation panel)
- A notification service (email/SMS/push)
- More robust safety protocols (multi-threshold policies, escalation, rate limiting)
- Model retraining pipeline + model registry/versioning
