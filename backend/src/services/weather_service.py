import time
import logging
import backend.src.config as config
from backend.src.http_client import http_session
from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.models.schema import StoreProfile

logger = logging.getLogger("autoreplenish.weather")


class WeatherService:
    def __init__(self, db_service: DynamoDBService = None):
        self.db = db_service or DynamoDBService()
        self.api_key = config.OPENWEATHER_API_KEY

    def get_weather_for_store(self, store: StoreProfile) -> dict:
        """
        Mengambil cuaca berdasarkan koordinat GPS toko:
        - Cache key spesifik menggabungkan zona dan grid koordinat (2 desimal).
        - Membedakan dengan tegas antara sumber 'OPENWEATHER_LIVE', 'DYNAMODB_CACHE', dan 'FALLBACK_ESTIMATE'.
        """
        now = int(time.time())
        lat_grid = f"{store.latitude:.2f}"
        lon_grid = f"{store.longitude:.2f}"
        cache_key = f"{store.zone}#{lat_grid}_{lon_grid}"

        # 1. Periksa Cache DynamoDB
        cached = self.db.get_weather_cache(cache_key)
        if cached:
            fetched_at = cached.get("fetched_at", 0)
            # Gunakan cache jika masih berlaku (< 3 jam / 10800 detik) dan bukan data fallback
            if now - fetched_at < 10800 and not cached.get("is_fallback", False):
                return {
                    "condition": cached.get("condition", "Cerah"),
                    "temperature_c": cached.get("temperature_c", 29.0),
                    "temperature_unit": "C",
                    "rain_probability": cached.get("rain_probability", 0.0),
                    "is_cached": True,
                    "is_fallback": False,
                    "source": "DYNAMODB_CACHE",
                    "fetched_at": fetched_at,
                }

        # 2. Jika API Key belum diisi, kembalikan status fallback eksplisit (tanpa disimpan ke cache)
        if not self.api_key:
            return {
                "condition": "Berawan (Estimasi Default)",
                "temperature_c": 29.0,
                "temperature_unit": "C",
                "rain_probability": 0.15,
                "is_cached": False,
                "is_fallback": True,
                "source": "FALLBACK_NO_API_KEY",
            }

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": store.latitude,
            "lon": store.longitude,
            "appid": self.api_key,
            "units": "metric",
            "lang": "id",
        }

        try:
            resp = http_session.get(url, params=params, timeout=(3.05, 6))
            if resp.status_code == 200:
                data = resp.json()
                temp = float(data.get("main", {}).get("temp", 28.0))
                condition = (
                    data.get("weather", [{}])[0]
                    .get("description", "Cerah")
                    .capitalize()
                )

                rain_1h = data.get("rain", {}).get("1h", 0.0)
                clouds = data.get("clouds", {}).get("all", 0)
                rain_prob = 0.8 if rain_1h > 0 else (0.5 if clouds > 70 else 0.1)

                weather_result = {
                    "condition": condition,
                    "temperature_c": temp,
                    "temperature_unit": "C",
                    "rain_probability": rain_prob,
                    "fetched_at": now,
                    "is_fallback": False,
                    "source": "OPENWEATHER_LIVE",
                }

                # Simpan ke DynamoDB dengan TTL 6 jam (21600 detik)
                self.db.save_weather_cache(cache_key, weather_result, now + 21600)
                weather_result["is_cached"] = False
                return weather_result

            logger.warning("OpenWeatherMap mengembalikan status HTTP %s", resp.status_code)
        except Exception as e:
            logger.error("Koneksi ke OpenWeatherMap gagal: %s", e)

        # Fallback eksplisit jika satelit cuaca gangguan (tidak disimpan ke cache)
        return {
            "condition": "Berawan (Fallback Transien)",
            "temperature_c": 28.5,
            "temperature_unit": "C",
            "rain_probability": 0.2,
            "is_cached": False,
            "is_fallback": True,
            "source": "FALLBACK_NETWORK_ERROR",
        }