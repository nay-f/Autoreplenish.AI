"""OpenWeatherMap integration + DynamoDB TTL cache tests (PRD Section 11.4, 14.3).

Verifies: real HTTP GET to OpenWeatherMap with each store's own coordinates (and
the generic fallback only when a store has none), correct field mapping
(main.temp / weather[0].description / rain), cache-hit avoidance of the external
call, stale-cache degradation, and full-unavailable fallback.
"""

import os
import sys
import time
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    moto_dynamo_table,
    FakeHTTPClient,
    FakeHTTPResponse,
    FakeSecretManager,
    owm_payload,
    TEST_TABLE_NAME,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.weather_service import WeatherService
from src.models.schema import StoreProfile
from src.config import WEATHER_CACHE_VALID_HOURS, WEATHER_SECRET_NAME, OPENWEATHERMAP_LAT, OPENWEATHERMAP_LON


def build_weather_service(table, http=None, api_key="test-owm-key"):
    db = DynamoDBService(table_name=TEST_TABLE_NAME, client=table)
    secret_service = FakeSecretManager({WEATHER_SECRET_NAME: {"api_key": api_key}})
    return WeatherService(db, secret_service=secret_service, http_client=http or FakeHTTPClient())


class TestWeatherServiceLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()
        cls.db = DynamoDBService(table_name=TEST_TABLE_NAME, client=cls.table)

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def setUp(self):
        # Clear the weather cache partition between tests.
        self.table.delete_item(Key={"PK": "ZONE#GROBOGAN_WIROSARI", "SK": "x"})

    def _clear_zone(self, zone):
        resp = self.table.scan()
        for item in resp.get("Items", []):
            if str(item.get("PK", "")).startswith(f"ZONE#{zone}"):
                self.table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    def tearDown(self):
        for zone in ("GROBOGAN_WIROSARI", "GROBOGAN_PURWODADI", "JAKARTA_PUSAT",
                     "SEMARANG_KOTA", "ZONA_TANPA_KOORDINAT"):
            self._clear_zone(zone)

    # ---------------------------------------------------------
    # Live API call
    # ---------------------------------------------------------
    def test_live_api_call_uses_the_stores_own_coordinates(self):
        http = FakeHTTPClient([
            FakeHTTPResponse(200, owm_payload(temp=28.7, description="light rain", rain_1h=1.4, humidity=84)),
            FakeHTTPResponse(200, owm_payload(temp=27.1, description="light rain", rain_1h=0.4, humidity=80)),
        ])
        service = build_weather_service(self.table, http=http)
        commercial = StoreProfile(
            store_id="STR-COMMERCIAL-01", store_name="Sentra Bisnis", zone="JAKARTA_PUSAT",
            latitude=-6.2088, longitude=106.8456,
        )
        residential = StoreProfile(
            store_id="STR-RESIDENTIAL-01", store_name="Residensial", zone="SEMARANG_KOTA",
            latitude=-6.9666, longitude=110.4166,
        )

        service.get_weather_for_store(commercial)
        service.get_weather_for_store(residential)

        self.assertEqual(len(http.calls), 2)
        first, second = http.calls
        self.assertEqual(first["method"], "GET")
        self.assertTrue(first["url"].endswith("/data/2.5/weather"), first["url"])
        self.assertAlmostEqual(first["params"]["lat"], -6.2088, places=4)
        self.assertAlmostEqual(first["params"]["lon"], 106.8456, places=4)
        self.assertAlmostEqual(second["params"]["lat"], -6.9666, places=4)
        self.assertAlmostEqual(second["params"]["lon"], 110.4166, places=4)
        self.assertEqual(first["params"]["appid"], "test-owm-key")
        self.assertEqual(first["params"]["units"], "metric")

    def test_field_mapping_matches_prd_14_3(self):
        """main.temp, weather[0].description and rain probability must be mapped."""
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload(
            temp=29.25, description="moderate rain", rain_1h=3.0, humidity=88
        ))])
        service = build_weather_service(self.table, http=http)

        ctx = service.get_weather_for_zone("GROBOGAN_WIROSARI")

        self.assertAlmostEqual(ctx.temperature_c, 29.25, places=2)
        self.assertEqual(ctx.condition, "Moderate Rain")
        self.assertGreater(ctx.rain_probability, 0.6)
        self.assertEqual(ctx.source, "OpenWeatherMap")
        self.assertFalse(ctx.is_stale)
        self.assertFalse(ctx.is_unavailable)
        self.assertIn("kelembapan", ctx.forecast)

    def test_dry_sky_uses_cloud_cover_as_weak_prior(self):
        http = FakeHTTPClient([FakeHTTPResponse(200, {
            "main": {"temp": 33.0, "humidity": 61},
            "weather": [{"description": "clear sky"}],
            "clouds": {"all": 10},
            "wind": {"speed": 2.0},
        })])
        service = build_weather_service(self.table, http=http)
        ctx = service.get_weather_for_zone("GROBOGAN_WIROSARI")
        self.assertEqual(ctx.condition, "Clear Sky")
        self.assertLess(ctx.rain_probability, 0.1)

    def test_api_call_error_raises_and_degrades(self):
        http = FakeHTTPClient([FakeHTTPResponse(500, {}, text="server error")])
        service = build_weather_service(self.table, http=http)
        with self.assertRaises(RuntimeError):
            service._fetch_live_weather("GROBOGAN_WIROSARI")

    # ---------------------------------------------------------
    # Caching (PRD 11.4)
    # ---------------------------------------------------------
    def test_second_read_is_served_from_dynamodb_cache(self):
        payload = owm_payload(temp=27.9, description="light rain", rain_1h=2.0)
        http = FakeHTTPClient([FakeHTTPResponse(200, payload)])
        service = build_weather_service(self.table, http=http)

        first = service.get_weather_for_zone("GROBOGAN_WIROSARI")
        self.assertEqual(len(http.calls), 1)

        second = service.get_weather_for_zone("GROBOGAN_WIROSARI")
        self.assertEqual(len(http.calls), 1)  # external API NOT called again
        self.assertAlmostEqual(second.temperature_c, first.temperature_c, places=2)
        self.assertIn(second.source, ("DynamoDB_Cache", "OpenWeatherMap"))

    def test_cache_entry_has_ttl_and_timestamp(self):
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload())])
        service = build_weather_service(self.table, http=http)
        service.get_weather_for_zone("GROBOGAN_WIROSARI")

        items = self.table.scan(
            FilterExpression="begins_with(PK, :pk)",
            ExpressionAttributeValues={":pk": "ZONE#GROBOGAN_WIROSARI"},
        )["Items"]
        self.assertTrue(items)
        item = items[0]
        self.assertIn("ttl", item)
        self.assertIn("cached_epoch", item)
        self.assertTrue(str(item["SK"]).startswith("WEATHER#"))

    def test_expired_cache_triggers_refetch(self):
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload(temp=25.0)),
                               FakeHTTPResponse(200, owm_payload(temp=31.5))])
        service = build_weather_service(self.table, http=http)

        service.get_weather_for_zone("GROBOGAN_WIROSARI")
        # Force the entry to look older than WEATHER_CACHE_VALID_HOURS.
        items = self.table.scan(
            FilterExpression="begins_with(PK, :pk)",
            ExpressionAttributeValues={":pk": "ZONE#GROBOGAN_WIROSARI"},
        )["Items"]
        stale_epoch = time.time() - (WEATHER_CACHE_VALID_HOURS * 3600) - 60
        for item in items:
            self.table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET #ce = :ce",
                ExpressionAttributeNames={"#ce": "cached_epoch"},
                ExpressionAttributeValues={":ce": Decimal(str(stale_epoch))},
            )

        refreshed = service.get_weather_for_zone("GROBOGAN_WIROSARI")
        self.assertEqual(len(http.calls), 2)
        self.assertAlmostEqual(refreshed.temperature_c, 31.5, places=2)

    # ---------------------------------------------------------
    # Degraded modes
    # ---------------------------------------------------------
    def test_api_failure_serves_stale_cache(self):
        http = FakeHTTPClient([
            FakeHTTPResponse(200, owm_payload(temp=26.0, description="light rain")),
            FakeHTTPResponse(503, {}, text="unavailable"),
        ])
        service = build_weather_service(self.table, http=http)

        service.get_weather_for_zone("GROBOGAN_WIROSARI")

        items = self.table.scan(
            FilterExpression="begins_with(PK, :pk)",
            ExpressionAttributeValues={":pk": "ZONE#GROBOGAN_WIROSARI"},
        )["Items"]
        for item in items:  # age it out of the 3h validity window
            self.table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET #ce = :ce",
                ExpressionAttributeNames={"#ce": "cached_epoch"},
                ExpressionAttributeValues={":ce": Decimal(str(time.time() - 5 * 3600))},
            )

        ctx = service.get_weather_for_zone("GROBOGAN_WIROSARI")
        self.assertTrue(ctx.is_stale)
        self.assertEqual(ctx.source, "Stale_Cache_Fallback")
        self.assertAlmostEqual(ctx.temperature_c, 26.0, places=2)
        self.assertIn("[Data Lama]", ctx.forecast)

    def test_total_outage_flags_unavailable(self):
        http = FakeHTTPClient([FakeHTTPResponse(500, {}, text="down")])
        service = build_weather_service(self.table, http=http)
        ctx = service.get_weather_for_zone("GROBOGAN_PURWODADI")

        self.assertTrue(ctx.is_unavailable)
        self.assertFalse(ctx.is_stale)
        self.assertIn("Tidak Tersedia", ctx.condition)

    def test_missing_api_key_disables_live_call(self):
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload())])
        service = build_weather_service(self.table, http=http, api_key="")
        with self.assertRaises(RuntimeError):
            service._fetch_live_weather("GROBOGAN_WIROSARI")
        self.assertEqual(len(http.calls), 0)

    def test_store_without_coordinates_falls_back_to_generic_default(self):
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload())])
        service = build_weather_service(self.table, http=http)
        store = StoreProfile(
            store_id="STR-NO-GEO", store_name="Tanpa Lokasi", zone="ZONA_TANPA_KOORDINAT",
        )
        service.get_weather_for_store(store)
        self.assertAlmostEqual(http.calls[0]["params"]["lat"], float(OPENWEATHERMAP_LAT), places=4)
        self.assertAlmostEqual(http.calls[0]["params"]["lon"], float(OPENWEATHERMAP_LON), places=4)

    def test_out_of_range_store_coordinates_fall_back_to_generic_default(self):
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload())])
        service = build_weather_service(self.table, http=http)
        store = StoreProfile(
            store_id="STR-BAD-GEO", store_name="Lokasi Rusak", zone="ZONA_TANPA_KOORDINAT",
            latitude=123.0, longitude=999.0,
        )
        service.get_weather_for_store(store)
        self.assertAlmostEqual(http.calls[0]["params"]["lat"], float(OPENWEATHERMAP_LAT), places=4)

    def test_api_key_resolved_from_secrets_manager(self):
        db = DynamoDBService(table_name=TEST_TABLE_NAME, client=self.table)
        secret_service = FakeSecretManager({WEATHER_SECRET_NAME: {"api_key": "secret-sourced-key"}})
        http = FakeHTTPClient([FakeHTTPResponse(200, owm_payload())])
        service = WeatherService(db, secret_service=secret_service, http_client=http)
        service.get_weather_for_zone("GROBOGAN_PURWODADI")
        self.assertEqual(http.calls[0]["params"]["appid"], "secret-sourced-key")


if __name__ == "__main__":
    unittest.main()
