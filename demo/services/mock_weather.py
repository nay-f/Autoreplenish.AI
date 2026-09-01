"""Mock Weather Service (OpenWeatherMap replacement) for AutoReplenish.ai Demo.

Returns deterministic weather data per geographical zone without calling external APIs.
"""

from datetime import datetime, timezone
from typing import Dict, Any

MOCK_ZONE_WEATHER = {
    "JAKARTA_PUSAT": {
        "condition": "Hujan deras",
        "temperature_c": 27.0,
        "rain_probability": 0.8,
        "forecast": "Hujan pada Sabtu-Minggu",
        "forecast_summary": "Hujan lebat disertai kilat",
        "humidity": 85,
    },
    "JAKARTA_SELATAN": {
        "condition": "Berawan",
        "temperature_c": 29.0,
        "rain_probability": 0.3,
        "forecast": "Berawan sepanjang hari",
        "forecast_summary": "Kondisi stabil berawan",
        "humidity": 70,
    },
    "DEPOK": {
        "condition": "Cerah berawan",
        "temperature_c": 31.0,
        "rain_probability": 0.1,
        "forecast": "Cerah hingga sore hari",
        "forecast_summary": "Cerah berawan tanpa potensi hujan signifikan",
        "humidity": 65,
    },
}

DEFAULT_WEATHER = {
    "condition": "Cerah berawan",
    "temperature_c": 28.5,
    "rain_probability": 0.2,
    "forecast": "Normal",
    "forecast_summary": "Kondisi cuaca tipikal",
    "humidity": 75,
}


def get_weather_for_zone(zone: str) -> Dict[str, Any]:
    """
    Retrieve deterministic weather forecast for a specified store zone.
    
    Returns:
        dict matching external weather context schema.
    """
    normalized_zone = zone.strip().upper() if zone else "JAKARTA_PUSAT"
    data = MOCK_ZONE_WEATHER.get(normalized_zone, DEFAULT_WEATHER).copy()
    
    data["zone"] = normalized_zone
    data["source"] = "mock_weather"
    data["weather_stale"] = False
    data["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return data
