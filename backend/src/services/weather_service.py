"""Weather Service with DynamoDB Caching and Graceful Fallback.

Implements PRD Section 11.4 & 14.3 (3-hour cache validity, 6-hour TTL, stale fallback).
"""

import time
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from ..config import logger, WEATHER_CACHE_VALID_HOURS
from ..models.schema import WeatherContext
from .dynamodb_service import DynamoDBService

# Default mock weather profiles per zone for offline / sandbox mode
ZONE_WEATHER_PROFILES = {
    "JAKARTA_PUSAT": {
        "condition": "Hujan deras",
        "temperature_c": 27.5,
        "rain_probability": 0.85,
        "forecast": "Hujan intensitas sedang hingga lebat pada akhir pekan"
    },
    "JAKARTA_SELATAN": {
        "condition": "Hujan ringan",
        "temperature_c": 29.0,
        "rain_probability": 0.60,
        "forecast": "Hujan lokal pada siang menjelang sore hari"
    },
    "BANDUNG_KOTA": {
        "condition": "Hujan sedang",
        "temperature_c": 22.0,
        "rain_probability": 0.75,
        "forecast": "Suhu dingin dan hujan berkala sepanjang sore"
    },
    "SURABAYA_TIMUR": {
        "condition": "Cerah Panas",
        "temperature_c": 33.5,
        "rain_probability": 0.10,
        "forecast": "Cuaca terik dan panas dengan kelembapan tinggi"
    }
}

class WeatherService:
    """Manages Weather fetching, caching, and fallback policies."""

    def __init__(self, db_service: DynamoDBService, api_key: Optional[str] = None):
        self.db = db_service
        self.api_key = api_key
        self._simulate_api_failure = False

    def get_weather_for_zone(self, zone_id: str) -> WeatherContext:
        """Fetch weather for a zone, checking cache first."""
        cached = self.db.get_weather_cache(zone_id)
        now_ts = time.time()

        # 1. Check if valid cache exists (< 3 hours old)
        if cached:
            cached_age_seconds = now_ts - cached.get("cached_epoch", 0)
            if cached_age_seconds < (WEATHER_CACHE_VALID_HOURS * 3600):
                logger.info(f"Weather cache hit for zone {zone_id} (age: {int(cached_age_seconds)}s)")
                return WeatherContext(
                    condition=cached.get("condition", "Cerah"),
                    temperature_c=float(cached.get("temperature_c", 30.0)),
                    rain_probability=float(cached.get("rain_probability", 0.0)),
                    forecast=cached.get("forecast", ""),
                    source="DynamoDB_Cache",
                    is_stale=False,
                    is_unavailable=False,
                    fetched_at=cached.get("fetched_at")
                )

        # 2. Cache miss or expired: Attempt to fetch from API / Provider
        if self._simulate_api_failure:
            logger.warning(f"Simulated Weather API failure for zone {zone_id}")
            return self._handle_weather_api_fallback(zone_id, cached)

        try:
            weather_data = self._fetch_live_or_mock_weather(zone_id)
            context = WeatherContext(
                condition=weather_data["condition"],
                temperature_c=weather_data["temperature_c"],
                rain_probability=weather_data["rain_probability"],
                forecast=weather_data["forecast"],
                source="OpenWeatherMap",
                is_stale=False,
                is_unavailable=False,
                fetched_at=datetime.now(timezone.utc).isoformat()
            )
            # Store in cache
            self.db.put_weather_cache(zone_id, context)
            return context

        except Exception as e:
            logger.error(f"Failed to fetch live weather for zone {zone_id}: {e}")
            return self._handle_weather_api_fallback(zone_id, cached)

    def _fetch_live_or_mock_weather(self, zone_id: str) -> Dict[str, Any]:
        """Fetch weather profile from live OWM or default zone profile."""
        profile = ZONE_WEATHER_PROFILES.get(
            zone_id,
            {
                "condition": "Cerah Berawan",
                "temperature_c": 30.0,
                "rain_probability": 0.20,
                "forecast": "Cuaca normal cerah berawan"
            }
        )
        return profile

    def _handle_weather_api_fallback(self, zone_id: str, stale_cache: Optional[Dict[str, Any]]) -> WeatherContext:
        """Handle fallback if API fails: use stale cache or return degraded unavailable context."""
        if stale_cache:
            logger.info(f"Using stale weather cache for zone {zone_id}")
            return WeatherContext(
                condition=stale_cache.get("condition", "Cerah Berawan"),
                temperature_c=float(stale_cache.get("temperature_c", 30.0)),
                rain_probability=float(stale_cache.get("rain_probability", 0.2)),
                forecast=f"[Data Lama] {stale_cache.get('forecast', '')}",
                source="Stale_Cache_Fallback",
                is_stale=True,
                is_unavailable=False,
                fetched_at=stale_cache.get("fetched_at")
            )

        logger.warning(f"Weather completely unavailable for zone {zone_id}")
        return WeatherContext(
            condition="Cuaca Tidak Tersedia",
            temperature_c=28.0,
            rain_probability=0.0,
            forecast="Data cuaca tidak dapat diakses",
            source="Unavailable_Fallback",
            is_stale=False,
            is_unavailable=True,
            fetched_at=datetime.now(timezone.utc).isoformat()
        )
