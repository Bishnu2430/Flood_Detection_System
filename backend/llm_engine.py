from __future__ import annotations

import json
import time
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


def ollama_is_available(timeout_seconds: float | None = None) -> tuple[bool, str | None]:
    """Best-effort check that Ollama is reachable.

    Uses /api/tags which is cheap and doesn't require generating tokens.
    """
    timeout = float(timeout_seconds) if timeout_seconds is not None else float(settings.HEALTHCHECK_TIMEOUT_SECONDS)
    try:
        generate_url = _normalize_ollama_url(settings.OLLAMA_URL)
        parsed = urlparse(generate_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        url = base.rstrip("/") + "/api/tags"
        resp = requests.get(url, timeout=timeout)
        if not resp.ok:
            return False, f"HTTP {resp.status_code}: {resp.text}"
        return True, None
    except Exception as e:
        return False, str(e)


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


def ollama_stream(prompt: str):
    """Yield (chunk, final_stats) from Ollama's streaming generate API.

    - chunk: incremental token/text output (may be empty)
    - final_stats: dict when generation completes (otherwise None)
    """
    url = _normalize_ollama_url(settings.OLLAMA_URL)
    start = time.perf_counter()
    first_token_at: float | None = None
    last_obj: dict | None = None

    try:
        with requests.post(
            url,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
            },
            stream=True,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        ) as resp:
            if not resp.ok:
                yield "", {
                    "ok": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                    "model": settings.OLLAMA_MODEL,
                    "total_ms": int((time.perf_counter() - start) * 1000),
                }
                return

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                last_obj = obj
                chunk = obj.get("response") or ""
                if chunk and first_token_at is None:
                    first_token_at = time.perf_counter()

                done = bool(obj.get("done"))
                if done:
                    total_ms = int((time.perf_counter() - start) * 1000)
                    first_token_ms = (
                        int((first_token_at - start) * 1000)
                        if first_token_at is not None
                        else None
                    )

                    # Ollama may include eval counts/durations.
                    stats = {
                        "ok": True,
                        "model": obj.get("model") or settings.OLLAMA_MODEL,
                        "total_ms": total_ms,
                        "first_token_ms": first_token_ms,
                        "prompt_eval_count": obj.get("prompt_eval_count"),
                        "eval_count": obj.get("eval_count"),
                        "prompt_eval_duration_ns": obj.get("prompt_eval_duration"),
                        "eval_duration_ns": obj.get("eval_duration"),
                        "total_duration_ns": obj.get("total_duration"),
                        "load_duration_ns": obj.get("load_duration"),
                    }
                    yield chunk, stats
                    return

                if chunk:
                    yield chunk, None

            # If stream ends unexpectedly, return best-effort stats.
            yield "", {
                "ok": False,
                "error": "stream_ended_unexpectedly",
                "model": settings.OLLAMA_MODEL,
                "last": last_obj,
                "total_ms": int((time.perf_counter() - start) * 1000),
            }

    except Exception as e:
        yield "", {
            "ok": False,
            "error": f"LLM unavailable: {e}",
            "model": settings.OLLAMA_MODEL,
            "total_ms": int((time.perf_counter() - start) * 1000),
        }


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
