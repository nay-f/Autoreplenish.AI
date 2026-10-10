"""Real DynamoDB SDK tests (moto-emulated, no in-memory dicts).

Verifies the single-table access patterns from PRD Section 13: PK/SK item
addressing, GSI1 entity listing, GSI2 business-key lookup, reverse-range
weather cache reads, TTL handling, and the SHORT_PROFILE counter.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    moto_dynamo_table,
    almadina_store,
    sku_perishable_fragile,
    sku_non_perishable,
    TEST_TABLE_NAME,
)
from src.services.dynamodb_service import DynamoDBService
from src.models.schema import (
    WeatherContext,
    TelegramStateRecord,
    AuditLogRecord,
    FeedbackLogRecord,
    SapTransactionRecord,
)
from datetime import datetime, timezone, timedelta


class TestDynamoDBSingleTable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()
        cls.db = DynamoDBService(table_name=TEST_TABLE_NAME, client=cls.table)

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    # -- store & sku ----------------------------------------------------
    def test_put_and_get_store(self):
        store = almadina_store()
        self.db.put_store(store)
        fetched = self.db.get_store("STR-ALMADINA-001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.store_name, "Toko Almadina Sembako")
        self.assertEqual(fetched.zone, "GROBOGAN_WIROSARI")
        self.assertIn("Wirosari", fetched.address)

    def test_list_all_stores_via_gsi1(self):
        store = almadina_store()
        self.db.put_store(store)
        stores = self.db.list_all_stores()
        self.assertTrue(any(s.store_id == "STR-ALMADINA-001" for s in stores))

    def test_put_and_get_sku(self):
        sku = sku_perishable_fragile()
        self.db.put_sku(sku)
        fetched = self.db.get_sku("SKU-ALM-003")
        self.assertEqual(fetched.shelf_life_days, 14)
        self.assertTrue(fetched.is_fragile)
        self.assertEqual(fetched.moq, 10)

    def test_list_all_skus_via_gsi1(self):
        self.db.put_sku(sku_perishable_fragile())
        self.db.put_sku(sku_non_perishable())
        skus = {s.sku_id for s in self.db.list_all_skus()}
        self.assertIn("SKU-ALM-003", skus)
        self.assertIn("SKU-ALM-001", skus)

    # -- weather cache (PRD 11.4) ---------------------------------------
    def test_weather_cache_roundtrip(self):
        weather = WeatherContext(
            condition="Hujan Ringan",
            temperature_c=28.4,
            rain_probability=0.62,
            forecast="Berawan dengan hujan lokal",
            source="OpenWeatherMap",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.put_weather_cache("GROBOGAN_WIROSARI", weather)
        cached = self.db.get_weather_cache("GROBOGAN_WIROSARI")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["condition"], "Hujan Ringan")
        self.assertAlmostEqual(cached["rain_probability"], 0.62, places=3)
        self.assertIn("ttl", cached)
        self.assertIn("cached_epoch", cached)

    def test_weather_cache_returns_newest_first(self):
        """Reverse-range scan: the freshest entry must win (PRD 11.4)."""
        zone = "GROBOGAN_PURWODADI"
        for temperature in (30.0, 27.5, 33.25):
            self.db.put_weather_cache(zone, WeatherContext(
                condition=f"Suhu {temperature}",
                temperature_c=temperature,
                rain_probability=0.1,
                forecast="",
                fetched_at=datetime.now(timezone.utc).isoformat(),
            ))
            time.sleep(0.02)  # ensure distinct sortable SK values
        cached = self.db.get_weather_cache(zone)
        self.assertAlmostEqual(cached["temperature_c"], 33.25, places=2)

    def test_weather_cache_miss_for_unknown_zone(self):
        self.assertIsNone(self.db.get_weather_cache("ZONE_TIDAK_ADA"))

    def test_weather_cache_ttl_stored_for_6_hours(self):
        from src.config import WEATHER_CACHE_TTL_HOURS

        before = time.time()
        self.db.put_weather_cache("SEMARANG_KOTA", WeatherContext(
            condition="Cerah", temperature_c=31.0, rain_probability=0.05,
            forecast="", fetched_at=datetime.now(timezone.utc).isoformat(),
        ))
        item = self.db.get_weather_cache("SEMARANG_KOTA")
        self.assertGreaterEqual(item["ttl"], before + (WEATHER_CACHE_TTL_HOURS * 3600) - 5)
        self.assertLessEqual(item["ttl"], before + (WEATHER_CACHE_TTL_HOURS * 3600) + 5)

    # -- telegram state machine ----------------------------------------
    def _state(self, request_id="REQ-TEST-0001", status="PENDING_APPROVAL"):
        now = datetime.now(timezone.utc)
        return TelegramStateRecord(
            request_id=request_id,
            run_id="RUN-TEST-0001",
            store_id="STR-ALMADINA-001",
            sku_id="SKU-ALM-003",
            recommended_qty=24,
            telegram_chat_id="1181431005",
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=4)).isoformat(),
            status=status,
        )

    def test_telegram_state_roundtrip_and_update(self):
        state = self._state()
        self.db.put_telegram_state(state)
        fetched = self.db.get_telegram_state("REQ-TEST-0001")
        self.assertEqual(fetched.status, "PENDING_APPROVAL")

        updated = self.db.update_telegram_state_status(
            "REQ-TEST-0001", "PR_CREATED", sap_pr_id="0014500012345"
        )
        self.assertEqual(updated.status, "PR_CREATED")
        self.assertEqual(updated.sap_pr_id, "0014500012345")
        self.assertEqual(self.db.get_telegram_state("REQ-TEST-0001").status, "PR_CREATED")

    def test_update_state_sets_awaiting_input(self):
        self.db.put_telegram_state(self._state("REQ-TEST-0002"))
        updated = self.db.update_telegram_state_status(
            "REQ-TEST-0002", "PENDING_APPROVAL", awaiting_input="QTY"
        )
        self.assertEqual(updated.awaiting_input, "QTY")

    # -- audit log ------------------------------------------------------
    def _audit(self, request_id="REQ-AUDIT-0001"):
        return AuditLogRecord(
            request_id=request_id,
            run_id="RUN-TEST-0001",
            store_id="STR-ALMADINA-001",
            store_name="Toko Almadina Sembako",
            area_type="Sub-Urban / Sentra Pemukiman Kecamatan",
            sku_id="SKU-ALM-003",
            sku_name="Telur Ayam Ras Segar 1kg",
            category="Perishable",
            physical_stock=4,
            threshold=12,
            average_daily_burn_rate=8.0,
            lead_time_days=1,
            moq=10,
            packaging_multiple=10,
            weather_condition="Hujan Ringan",
            weather_source="OpenWeatherMap",
            weather_stale=False,
            calendar_day="Weekend",
            is_public_holiday=False,
            is_payday=False,
            promo_active=False,
            created_at=datetime.now(timezone.utc).isoformat(),
            ai_recommended_qty=20,
            final_recommended_qty=20,
            is_fallback=False,
        )

    def test_audit_log_roundtrip_and_gsi2_lookup(self):
        self.db.put_audit_log(self._audit("REQ-AUDIT-0001"))
        fetched = self.db.get_audit_log_by_request_id("REQ-AUDIT-0001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.sku_id, "SKU-ALM-003")
        self.assertEqual(fetched.sap_pr_status, "PENDING")
        self.assertFalse(fetched.is_fallback)

    def test_audit_log_missing_optional_fields_not_persisted(self):
        """None-valued optional fields must be dropped, not stored as null."""
        self.db.put_audit_log(self._audit("REQ-AUDIT-0002"))
        resp = self.table.get_item(Key={"PK": "AUDIT#STR-ALMADINA-001",
                                       "SK": self.db.get_audit_log_by_request_id("REQ-AUDIT-0002").SK})
        item = resp["Item"]
        self.assertNotIn("human_action", item)
        self.assertIn("GSI1PK", item)
        self.assertIn("GSI2PK", item)

    def test_list_audit_logs_filtered_by_store(self):
        self.db.put_audit_log(self._audit("REQ-AUDIT-0003"))
        logs = self.db.list_audit_logs(store_id="STR-ALMADINA-001", limit=10)
        self.assertTrue(logs)
        self.assertTrue(all(l.store_id == "STR-ALMADINA-001" for l in logs))

    # -- feedback -------------------------------------------------------
    def test_feedback_roundtrip_and_recent_lookup(self):
        fb = FeedbackLogRecord(
            store_id="STR-ALMADINA-001",
            sku_id="SKU-ALM-003",
            action="REJECTED",
            reason="Stok di gudang belakang masih ada",
            original_recommended_qty=20,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.put_feedback_log(fb)
        recent = self.db.list_recent_feedback("STR-ALMADINA-001", "SKU-ALM-003", limit=3)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].action, "REJECTED")
        self.assertEqual(len(self.db.list_all_feedbacks()), 1)

    # -- chat pointer ---------------------------------------------------
    def test_chat_pending_request_pointer(self):
        self.db.set_chat_pending_request("1181431005", "REQ-CHAT-0001")
        self.assertEqual(self.db.get_chat_pending_request("1181431005"), "REQ-CHAT-0001")
        self.db.clear_chat_pending_request("1181431005")
        self.assertIsNone(self.db.get_chat_pending_request("1181431005"))

    # -- sap transaction ledger ----------------------------------------
    def test_sap_transaction_roundtrip(self):
        txn = SapTransactionRecord(
            request_id="REQ-SAP-0001",
            store_id="STR-ALMADINA-001",
            sku_id="SKU-ALM-003",
            quantity=20,
            status="SUCCESS",
            sap_pr_id="0014500012345",
            mode="PERSISTENT_SANDBOX",
            created_at=datetime.now(timezone.utc).isoformat(),
            response_payload={"d": {"PurchaseRequisition": "0014500012345"}},
        )
        self.db.put_sap_transaction(txn)
        fetched = self.db.get_sap_transaction("REQ-SAP-0001")
        self.assertEqual(fetched.sap_pr_id, "0014500012345")
        self.assertEqual(fetched.mode, "PERSISTENT_SANDBOX")
        self.assertEqual(len(self.db.list_sap_transactions()), 1)

    # -- counter --------------------------------------------------------
    def test_atomic_pr_counter_is_monotonic(self):
        values = [self.db.next_sap_pr_sequence() for _ in range(5)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(len(set(values)), 5)


if __name__ == "__main__":
    unittest.main()
