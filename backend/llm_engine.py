from __future__ import annotations

from urllib.parse import urlparse

import requests

from .config import settings


def _normalize_ollama_url(url: str) -> str:
    # Accept either full endpoint (..../api/generate) or base host (http://localhost:11434)
    # and normalize to /api/generate.
    parsed = urlparse(url)
    path = parsed.path or ""
    if path.rstrip("/") in ("", "/api"):
        return url.rstrip("/") + "/api/generate"
    return url


def ollama_generate(prompt: str) -> str:
    url = _normalize_ollama_url(settings.OLLAMA_URL)
    try:
        response = requests.post(
            url,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )
        if not response.ok:
            # Common case: model not pulled yet -> 404 with JSON error.
            return f"LLM error {response.status_code}: {response.text}"
        return response.json().get("response", "") or ""
    except Exception as e:
        return f"LLM unavailable: {e}"


def generate_explanation(sensor_data, risk, probability):

    distance_cm = sensor_data.get("distance_cm", sensor_data.get("height"))
    rain_analog = sensor_data.get("rain_analog", sensor_data.get("rain"))
    float_status = sensor_data.get("float_status", sensor_data.get("float"))

    prompt = f"""
You are a Flood Risk Intelligence Agent.

Current Sensor Data:
Water Height/Distance: {distance_cm} cm
Rain Level: {rain_analog}
Float Triggered: {float_status}

Predicted Risk Level: {risk}
Probability: {probability:.2f}

Explain the flood risk clearly and recommend safety actions.
"""

    result = ollama_generate(prompt)
    return result or "No explanation generated."
