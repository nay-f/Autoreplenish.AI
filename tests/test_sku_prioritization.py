"""SKU Prioritization tests (PRD Section 11.2 / FR-02).

Validates the 9 prioritization criteria using the generic multi-store FMCG seed
catalogue (backend/src/data/seed_*.json), including the shelf-life and weather
signals.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    moto_dynamo_table, FakeBedrockClient, FakeHTTPClient,
    FakeHTTPResponse, owm_payload, TEST_TABLE_NAME,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.weather_service import WeatherService
from src.services.calendar_promo_service import CalendarPromoService
from src.services.bedrock_service import BedrockReasoningService
from src.services.telegram_service import TelegramService
from src.services.orchestrator_service import OrchestratorService
from src.data.master_data_loader import (
    load_seed_skus,
    load_seed_stock_levels,
    load_seed_stores,
)

SEED_STORES = load_seed_stores()
SEED_SKUS = load_seed_skus()
SEED_STOCK = load_seed_stock_levels()
COMMERCIAL_ID = "STR-COMMERCIAL-01"
RESIDENTIAL_ID = "STR-RESIDENTIAL-01"


def seed_store(store_id):
    return next(s for s in SEED_STORES if s.store_id == store_id)


def weather_http():
    return FakeHTTPClient([
        FakeHTTPResponse(200, owm_payload(temp=28.0, description="light rain", rain_1h=1.0))
        for _ in range(10)
    ])


def build_orchestrator():
    db = DynamoDBService(table_name=TEST_TABLE_NAME)
    return OrchestratorService(
        db_service=db,
        weather_service=WeatherService(db, api_key="test", http_client=weather_http()),
        calendar_promo_service=CalendarPromoService(),
        bedrock_service=BedrockReasoningService(bedrock_client=FakeBedrockClient()),
        telegram_service=TelegramService(bot_token="T"),
    ), db


class TestSkuPrioritization(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()
        cls.orchestrator, cls.db = build_orchestrator()

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def test_catalogue_contains_four_generic_fmcg_skus(self):
        self.assertEqual(len(SEED_SKUS), 4)
        names = {s.sku_name for s in SEED_SKUS}
        self.assertIn("Roti Manis Cokelat", names)
        self.assertIn("Beras Premium 5kg", names)
        self.assertIn("Minyak Goreng 2L", names)
        self.assertIn("Minuman Isotonik Dingin 500ml", names)

    def test_seed_stores_master_data(self):
        self.assertEqual([s.store_id for s in SEED_STORES], [COMMERCIAL_ID, RESIDENTIAL_ID])

        commercial = seed_store(COMMERCIAL_ID)
        self.assertEqual(commercial.store_name, "Minimarket Cabang Sentra Bisnis")
        self.assertEqual(commercial.area_type, "Komersial / Perkantoran")
        self.assertAlmostEqual(commercial.latitude, -6.2088, places=4)
        self.assertAlmostEqual(commercial.longitude, 106.8456, places=4)

        residential = seed_store(RESIDENTIAL_ID)
        self.assertEqual(residential.store_name, "Minimarket Cabang Residensial")
        self.assertEqual(residential.area_type, "Pemukiman Warga")
        self.assertAlmostEqual(residential.latitude, -6.9666, places=4)
        self.assertAlmostEqual(residential.longitude, 110.4166, places=4)

    def test_sku_commercial_constraints(self):
        by_id = {s.sku_id: s for s in SEED_SKUS}
        self.assertEqual(by_id["SKU-FMCG-001"].moq, 12)    # 12 pcs roti
        self.assertEqual(by_id["SKU-FMCG-001"].category, "Perishable")
        self.assertEqual(by_id["SKU-FMCG-001"].shelf_life_days, 3)
        self.assertEqual(by_id["SKU-FMCG-002"].moq, 5)     # 5 karung beras
        self.assertEqual(by_id["SKU-FMCG-002"].base_unit, "KARUNG")
        self.assertEqual(by_id["SKU-FMCG-003"].moq, 6)     # 6 pouch minyak
        self.assertEqual(by_id["SKU-FMCG-004"].moq, 24)    # 24 botol isotonik
        self.assertTrue(by_id["SKU-FMCG-004"].weather_sensitive)
        self.assertEqual(by_id["SKU-FMCG-002"].category, "Non-Perishable")
        self.assertEqual(by_id["SKU-FMCG-003"].category, "Non-Perishable")

    def test_skus_below_threshold_are_selected(self):
        store = seed_store(COMMERCIAL_ID)
        stock = SEED_STOCK[COMMERCIAL_ID]

        priority = self.orchestrator.prioritize_skus(store, SEED_SKUS, stock)
        selected = {p.sku_id for p in priority}

        # Every SKU seeded below its threshold must be prioritised.
        for sku_id, levels in stock.items():
            if levels["physical_stock"] < levels["threshold"]:
                self.assertIn(sku_id, selected)

    def test_short_shelf_life_adds_priority(self):
        store = seed_store(COMMERCIAL_ID)
        stock = {
            "SKU-FMCG-001": {"physical_stock": 17, "threshold": 25, "average_daily_burn_rate": 12.0,
                             "lead_time_days": 1, "open_pr_qty": 0},
            "SKU-FMCG-002": {"physical_stock": 17, "threshold": 25, "average_daily_burn_rate": 12.0,
                             "lead_time_days": 1, "open_pr_qty": 0},
        }
        priority = {
            p.sku_id: p for p in self.orchestrator.prioritize_skus(store, SEED_SKUS, stock)
        }

        # Roti (3-day shelf life, perishable) must outrank beras (365-day).
        self.assertGreater(
            priority["SKU-FMCG-001"].priority_score,
            priority["SKU-FMCG-002"].priority_score,
        )
        self.assertIn("short_shelf_life_3d", priority["SKU-FMCG-001"].reason_codes)
        self.assertIn("perishable", priority["SKU-FMCG-001"].reason_codes)

    def test_weather_sensitive_adds_priority(self):
        store = seed_store(COMMERCIAL_ID)
        stock = SEED_STOCK[COMMERCIAL_ID]
        priority = {
            p.sku_id: p for p in self.orchestrator.prioritize_skus(store, SEED_SKUS, stock)
        }
        self.assertIn("weather_sensitive", priority["SKU-FMCG-004"].reason_codes)
        self.assertNotIn("weather_sensitive", priority["SKU-FMCG-003"].reason_codes)

    def test_healthy_stock_is_not_selected(self):
        store = seed_store(COMMERCIAL_ID)
        healthy = {
            "SKU-FMCG-002": {"physical_stock": 500, "threshold": 15, "average_daily_burn_rate": 3.0,
                             "lead_time_days": 3, "open_pr_qty": 0},
        }
        priority = self.orchestrator.prioritize_skus(store, SEED_SKUS, healthy)
        self.assertNotIn("SKU-FMCG-002", {p.sku_id for p in priority})

    def test_priority_scores_are_capped_at_100_and_sorted(self):
        store = seed_store(RESIDENTIAL_ID)
        stock = SEED_STOCK[RESIDENTIAL_ID]
        priority = self.orchestrator.prioritize_skus(store, SEED_SKUS, stock)

        self.assertTrue(priority)
        self.assertTrue(all(p.priority_score <= 100 for p in priority))
        scores = [p.priority_score for p in priority]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_context_carries_shelf_life_and_store_location_to_the_engine(self):
        store = seed_store(RESIDENTIAL_ID)
        stock = SEED_STOCK[RESIDENTIAL_ID]
        priority = {
            p.sku_id: p for p in self.orchestrator.prioritize_skus(store, SEED_SKUS, stock)
        }
        roti_ctx = priority["SKU-FMCG-001"].context
        self.assertEqual(roti_ctx.sku.shelf_life_days, 3)
        self.assertEqual(roti_ctx.store.store_id, RESIDENTIAL_ID)
        self.assertAlmostEqual(roti_ctx.store.latitude, -6.9666, places=4)

    def test_orchestrator_defaults_come_from_the_json_loader(self):
        self.assertEqual({s.store_id for s in self.orchestrator.get_stores()}
                         & {COMMERCIAL_ID, RESIDENTIAL_ID}, {COMMERCIAL_ID, RESIDENTIAL_ID})
        self.assertEqual({s.sku_id for s in self.orchestrator.get_skus()},
                         {s.sku_id for s in SEED_SKUS})
        self.assertEqual(self.orchestrator.get_opening_stock(COMMERCIAL_ID), SEED_STOCK[COMMERCIAL_ID])
        self.assertEqual(self.orchestrator.get_opening_stock("STR-UNKNOWN"), {})


if __name__ == "__main__":
    unittest.main()
