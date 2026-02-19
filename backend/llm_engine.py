import requests
from .config import settings

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

    response = requests.post(
        settings.OLLAMA_URL,
        json={
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json().get("response", "No explanation generated.")
