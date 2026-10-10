"""Weather Service with DynamoDB Caching, Live OpenWeatherMap, and Fallback.

Implements PRD Section 11.4 (cache policy) and 14.3 (data mapping):
    - Cache per store zone, valid 3 hours, DynamoDB TTL 6 hours.
    - On cache miss/expiry: real HTTP GET to OpenWeatherMap using the store's own
      latitude/longitude (generic fallback coordinates only when the store has none).
    - On API failure: serve the last cached snapshot flagged ``is_stale=True``.
    - On total unavailability: return a degraded ``is_unavailable=True`` context
      so the reasoning engine lowers its confidence instead of crashing.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

from ..config import (
    logger,
    WEATHER_CACHE_VALID_HOURS,
    WEATHER_SECRET_NAME,
    OPENWEATHERMAP_BASE_URL,
    OPENWEATHERMAP_LAT,
    OPENWEATHERMAP_LON,
    OPENWEATHERMAP_UNITS,
    OPENWEATHERMAP_TIMEOUT_SECONDS,
    OPENWEATHERMAP_MAX_RETRIES,
)
from ..models.schema import StoreMetadata, WeatherContext
from .dynamodb_service import DynamoDBService
from .secrets_service import SecretManagerService

# Last-resort default used only when every upstream source is unavailable.
DEGRADED_CONDITION = "Cuaca Tidak Tersedia"


class WeatherService:
    """Manages weather fetching, caching, and fallback policies."""

    def __init__(
        self,
        db_service: DynamoDBService,
        api_key: Optional[str] = None,
        secret_service: Optional[SecretManagerService] = None,
        http_client: Optional[Any] = None,
    ):
        """
        Args:
            db_service: DynamoDB accessor (cache source of truth).
            api_key: OpenWeatherMap key. When omitted it is resolved from
                Secrets Manager at first use.
            secret_service: Injectable SecretManagerService (for tests).
            http_client: Injectable object exposing ``.get(url, params, timeout)``.
        """
        self.db = db_service
        self._api_key = api_key
        self._secret_service = secret_service
        self._http = http_client or requests
        self.api_calls_this_invocation = 0  # observable: guards against over-calling

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def get_weather_for_store(self, store: StoreMetadata) -> WeatherContext:
        """Fetch weather for a store using its own coordinates.

        The cache is keyed by the store's zone (PRD 11.4); the live request uses
        ``store.latitude`` / ``store.longitude``. Generic fallback coordinates are
        used only when the store has no (valid) location data.
        """
        latitude, longitude = self._resolve_coordinates(
            store.latitude, store.longitude, owner=f"store '{store.store_id}'"
        )
        return self.get_weather_for_zone(
            store.zone or store.store_id, latitude=latitude, longitude=longitude
        )

    def get_weather_for_zone(
        self,
        zone_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> WeatherContext:
        """Fetch weather for a zone, checking the DynamoDB cache first.

        ``latitude``/``longitude`` select the live-request location; when omitted
        the generic fallback coordinates are used.
        """
        cached = self.db.get_weather_cache(zone_id)
        now_ts = time.time()

        # 1. Valid cache hit (< 3 hours old) - PRD 11.4
        if cached:
            cached_age_seconds = now_ts - float(cached.get("cached_epoch", 0))
            if cached_age_seconds < (WEATHER_CACHE_VALID_HOURS * 3600):
                logger.info(f"Weather cache HIT for zone {zone_id} (age {int(cached_age_seconds)}s)")
                return self._context_from_cache(cached)

        # 2. Cache miss or expired - attempt the live OpenWeatherMap API
        try:
            weather_data = self._fetch_live_weather(zone_id, latitude, longitude)
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
            self.db.put_weather_cache(zone_id, context)
            return context

        except Exception as e:
            logger.error(f"Failed to fetch live weather for zone {zone_id}: {e}")
            return self._handle_weather_api_fallback(zone_id, cached)

    # ---------------------------------------------------------
    # Live OpenWeatherMap
    # ---------------------------------------------------------
    def _resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        if self._secret_service is None:
            self._secret_service = SecretManagerService()
        self._api_key = self._secret_service.get_weather_api_key(WEATHER_SECRET_NAME)
        return self._api_key

    @staticmethod
    def _resolve_coordinates(
        latitude: Optional[float],
        longitude: Optional[float],
        owner: str = "request",
    ) -> Tuple[float, float]:
        """Return usable (lat, lon), falling back to the generic default if absent/invalid."""
        if latitude is not None and longitude is not None:
            try:
                lat, lon = float(latitude), float(longitude)
            except (TypeError, ValueError):
                logger.warning(f"Non-numeric coordinates for {owner}; using generic fallback")
            else:
                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    return lat, lon
                logger.warning(
                    f"Out-of-range coordinates ({lat}, {lon}) for {owner}; using generic fallback"
                )
        else:
            logger.warning(f"No coordinates configured for {owner}; using generic fallback")
        return float(OPENWEATHERMAP_LAT), float(OPENWEATHERMAP_LON)

    def _fetch_live_weather(
        self,
        zone_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Call the OpenWeatherMap ``/weather`` endpoint and map PRD 14.3 fields."""
        api_key = self._resolve_api_key()
        if not api_key:
            raise RuntimeError("OpenWeatherMap API key is not configured (check Secrets Manager)")

        lat, lon = self._resolve_coordinates(latitude, longitude, owner=f"zone '{zone_id}'")
        url = f"{OPENWEATHERMAP_BASE_URL.rstrip('/')}/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": OPENWEATHERMAP_UNITS,
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, OPENWEATHERMAP_MAX_RETRIES + 1):
            try:
                self.api_calls_this_invocation += 1
                response = self._http.get(url, params=params, timeout=OPENWEATHERMAP_TIMEOUT_SECONDS)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"OpenWeatherMap returned HTTP {response.status_code}"
                    )
                payload = response.json()
                return self._map_openweathermap_payload(payload)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"OpenWeatherMap attempt {attempt}/{OPENWEATHERMAP_MAX_RETRIES} failed: {e}"
                )
                if attempt < OPENWEATHERMAP_MAX_RETRIES:
                    time.sleep(2 ** (attempt - 1))  # exponential backoff

        raise RuntimeError(f"OpenWeatherMap unreachable: {last_error}")

    def _map_openweathermap_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map the OpenWeatherMap response to PRD Section 14.3 field names."""
        if not isinstance(data, dict) or "main" not in data:
            raise ValueError("Malformed OpenWeatherMap payload (missing 'main')")

        main = data.get("main", {}) or {}
        weather_list = data.get("weather") or []
        if not weather_list:
            raise ValueError("Malformed OpenWeatherMap payload (missing 'weather[]')")

        temperature_c = float(main.get("temp", 30.0))
        condition = str(weather_list[0].get("description", "Tidak diketahui")).strip().title()
        rain_probability = self._derive_rain_probability(data)
        forecast = self._build_forecast_summary(data, condition, temperature_c, rain_probability)

        return {
            "condition": condition,
            "temperature_c": temperature_c,
            "rain_probability": rain_probability,
            "forecast": forecast,
        }

    @staticmethod
    def _derive_rain_probability(data: Dict[str, Any]) -> float:
        """Derive a 0..1 rain probability.

        OpenWeatherMap's current-weather endpoint exposes measured rainfall in
        ``rain.1h`` (mm) rather than a forecast probability, so intensity is
        rescaled into a probability band and cloud cover is used as a weak
        prior when no rainfall has been recorded.
        """
        rain_mm = 0.0
        rain_block = data.get("rain") or {}
        if isinstance(rain_block, dict):
            for key in ("1h", "3h"):
                if isinstance(rain_block.get(key), (int, float)):
                    rain_mm = max(rain_mm, float(rain_block[key]))

        if rain_mm > 0:
            # >=10mm/h is treated as near-certain heavy rain.
            return round(min(1.0, 0.5 + (rain_mm / 20.0)), 3)

        clouds = float((data.get("clouds") or {}).get("all", 0) or 0)
        return round(min(0.4, (clouds / 100.0) * 0.4), 3)

    @staticmethod
    def _build_forecast_summary(
        data: Dict[str, Any],
        condition: str,
        temperature_c: float,
        rain_probability: float
    ) -> str:
        humidity = (data.get("main") or {}).get("humidity")
        wind_ms = (data.get("wind") or {}).get("speed")
        parts = [f"{condition}, {temperature_c:.1f}°C"]

        if humidity is not None:
            parts.append(f"kelembapan {humidity}%")
        if wind_ms is not None:
            parts.append(f"angin {wind_ms:.1f} m/s")
        if rain_probability >= 0.6:
            parts.append("potensi hujan tinggi")
        elif rain_probability >= 0.3:
            parts.append("potensi hujan sedang")

        return "; ".join(parts)

    # ---------------------------------------------------------
    # Degraded-mode fallbacks (PRD Section 11.4)
    # ---------------------------------------------------------
    def _context_from_cache(self, cached: Dict[str, Any]) -> WeatherContext:
        return WeatherContext(
            condition=cached.get("condition", "Cerah Berawan"),
            temperature_c=float(cached.get("temperature_c", 30.0)),
            rain_probability=float(cached.get("rain_probability", 0.2)),
            forecast=cached.get("forecast", ""),
            source=cached.get("source", "DynamoDB_Cache"),
            is_stale=False,
            is_unavailable=False,
            fetched_at=cached.get("fetched_at"),
        )

    def _handle_weather_api_fallback(self, zone_id: str, stale_cache: Optional[Dict[str, Any]]) -> WeatherContext:
        """Serve the last cached snapshot, or flag weather as unavailable."""
        if stale_cache:
            logger.info(f"Serving stale weather cache for zone {zone_id}")
            return WeatherContext(
                condition=stale_cache.get("condition", "Cerah Berawan"),
                temperature_c=float(stale_cache.get("temperature_c", 30.0)),
                rain_probability=float(stale_cache.get("rain_probability", 0.2)),
                forecast=f"[Data Lama] {stale_cache.get('forecast', '')}",
                source="Stale_Cache_Fallback",
                is_stale=True,
                is_unavailable=False,
                fetched_at=stale_cache.get("fetched_at"),
            )

        logger.warning(f"Weather completely unavailable for zone {zone_id}")
        return WeatherContext(
            condition=DEGRADED_CONDITION,
            temperature_c=28.0,
            rain_probability=0.0,
            forecast="Data cuaca tidak dapat diakses",
            source="Unavailable_Fallback",
            is_stale=False,
            is_unavailable=True,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
