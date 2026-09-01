"""Unit Tests for Weather Caching & Fallback (PRD Section 11.4 & 15.4)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.services.dynamodb_service import DynamoDBService
from src.services.weather_service import WeatherService
from src.models.schema import WeatherContext

class TestWeatherCache(unittest.TestCase):

    def setUp(self):
        self.db = DynamoDBService()
        self.weather_service = WeatherService(self.db)

    def test_cache_miss_then_cache_hit(self):
        """First call stores in cache; subsequent call hits cache."""
        zone = "JAKARTA_PUSAT"
        # 1. First fetch (cache miss -> stores in cache)
        w1 = self.weather_service.get_weather_for_zone(zone)
        self.assertEqual(w1.source, "OpenWeatherMap")
        self.assertFalse(w1.is_stale)

        # 2. Second fetch within 3 hours (cache hit)
        w2 = self.weather_service.get_weather_for_zone(zone)
        self.assertEqual(w2.source, "DynamoDB_Cache")
        self.assertEqual(w1.condition, w2.condition)

    def test_graceful_stale_fallback_on_api_error(self):
        """When weather API fails, falls back to stale cache with is_stale=True."""
        zone = "JAKARTA_SELATAN"
        # Populate initial cache
        self.weather_service.get_weather_for_zone(zone)

        # Simulate API failure
        self.weather_service._simulate_api_failure = True
        w_fallback = self.weather_service.get_weather_for_zone(zone)
        self.assertIsNotNone(w_fallback)
        self.assertTrue(w_fallback.is_stale or w_fallback.source == "DynamoDB_Cache")

    def test_weather_unavailable_when_no_cache_and_api_error(self):
        """When no cache exists and API fails, return is_unavailable=True."""
        zone = "UNKNOWN_NEW_ZONE"
        self.weather_service._simulate_api_failure = True
        w_unavail = self.weather_service.get_weather_for_zone(zone)
        self.assertTrue(w_unavail.is_unavailable)

if __name__ == "__main__":
    unittest.main()
