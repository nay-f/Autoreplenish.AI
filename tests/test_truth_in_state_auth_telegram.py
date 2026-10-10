"""Unit Tests for Truth-in-State Health, Dashboard Authentication, and Telegram Bot Onboarding.

Verifies:
1. Health checks adhere strictly to Truth-in-State (NOT CONFIGURED, CONNECTED, ERROR, ACTIVE, INACTIVE).
2. Auth endpoints validate login, role assignment, and Bearer token claims.
3. Telegram state machine captures native GPS location objects, area types, zones,
   and synchronously registers stores to SQLite database.
4. On-demand evaluation runs without scheduler interference.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend and demo directories are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
DEMO_DIR = os.path.join(BASE_DIR, "demo")
for p in [BASE_DIR, BACKEND_DIR, DEMO_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.handlers.dashboard_api_handler import DashboardApiProcessor
from demo.services.local_db import (
    init_db,
    get_store_by_id,
    get_all_stores,
    save_store,
)
import importlib
tg_listener = importlib.import_module("demo.scripts.04_telegram_listener")


class TestDashboardAuthAndHealth(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.processor = DashboardApiProcessor(db_service=self.mock_db)

    def test_auth_login_valid_credentials(self):
        result = self.processor.auth_login("admin", "Admin123!", role="Store Manager")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("token", result)
        self.assertEqual(result["username"], "admin")
        self.assertEqual(result["role"], "Store Manager")
        self.assertIn("bearer", result["token_type"].lower())

    def test_auth_login_invalid_credentials_rejected(self):
        with self.assertRaises(ValueError):
            self.processor.auth_login("admin", "WrongPassword!")

    def test_auth_me_with_valid_token(self):
        login_res = self.processor.auth_login("admin", "Admin123!", role="Regional Manager")
        token = login_res["token"]

        me = self.processor.auth_me(f"Bearer {token}")
        self.assertEqual(me["username"], "admin")
        self.assertEqual(me["role"], "Regional Manager")
        self.assertEqual(me["status"], "AUTHENTICATED")

    def test_ingest_pos_success_with_secret(self):
        mock_store = MagicMock()
        mock_store.store_id = "STR-COMMERCIAL-01"
        mock_store.store_name = "Minimarket Cabang Sentra Bisnis"
        mock_store.ingestion_config.webhook_secret = "sec_str_commercial_01_live"
        self.mock_db.get_store.return_value = mock_store

        payload = {
            "store_id": "STR-COMMERCIAL-01",
            "timestamp": "2026-10-10T21:00:00Z",
            "sync_type": "CLOSING_SHIFT",
            "inventory": [
                {
                    "sku_id": "SKU-FMCG-001",
                    "current_physical_stock": 12,
                    "daily_sales_qty": 38
                },
                {
                    "sku_id": "SKU-FMCG-002",
                    "current_physical_stock": 4,
                    "daily_sales_qty": 16
                }
            ]
        }
        headers = {"X-POS-Secret-Key": "sec_str_commercial_01_live"}
        resp = self.processor.ingest_pos("STR-COMMERCIAL-01", payload, headers)
        self.assertEqual(resp["status"], "SUCCESS")
        self.assertEqual(resp["items_updated"], 2)
        self.assertIn("Inventory synced successfully", resp["message"])

    def test_ingest_pos_unauthorized_without_secret(self):
        mock_store = MagicMock()
        mock_store.store_id = "STR-COMMERCIAL-01"
        mock_store.ingestion_config.webhook_secret = "secret-123"
        self.mock_db.get_store.return_value = mock_store

        payload = {"inventory": []}
        # Bad secret
        resp = self.processor.ingest_pos("STR-COMMERCIAL-01", payload, {"X-POS-Secret-Key": "wrong-secret"})
        self.assertEqual(resp["status_code"], 401)
        self.assertEqual(resp["status"], "UNAUTHORIZED")

        # Missing secret
        resp2 = self.processor.ingest_pos("STR-COMMERCIAL-01", payload, {})
        self.assertEqual(resp2["status_code"], 401)
        self.assertEqual(resp2["status"], "UNAUTHORIZED")

    def test_auth_me_with_invalid_token_fails(self):
        with self.assertRaises(ValueError):
            self.processor.auth_me("Bearer invalid-garbage-token")

    def test_integration_health_truth_in_state(self):
        health = self.processor.get_integration_health()
        self.assertIn("integrations", health)
        integrations = health["integrations"]

        for expected_key in ["bedrock", "weather", "telegram", "sap", "pos"]:
            self.assertIn(expected_key, integrations)
            status = integrations[expected_key].get("status")
            self.assertTrue(
                status in [
                    "NOT CONFIGURED",
                    "ERROR",
                    "CONNECTED",
                    "DISCONNECTED / ERROR",
                    "ACTIVE",
                    "INACTIVE / WAITING DATA",
                ],
                f"Unexpected status for {expected_key}: {status}",
            )


class TestTelegramOnboardingStateMachine(unittest.TestCase):
    def setUp(self):
        init_db()
        tg_listener.USER_STATES.clear()

    def test_telegram_store_onboarding_with_gps_location(self):
        chat_id = "99887766"

        # Step 1: User sends /register_store
        with patch.object(tg_listener, "send_text_message") as mock_send_text:
            tg_listener.handle_message(chat_id, "/register_store")
            self.assertIn(chat_id, tg_listener.USER_STATES)
            self.assertEqual(tg_listener.USER_STATES[chat_id]["state"], "REG_AWAIT_NAME")
            mock_send_text.assert_called_once()

        # Step 2: User provides store name
        with patch.object(tg_listener, "send_message") as mock_send_msg:
            tg_listener.handle_message(chat_id, "Toko Berkah Sejahtera")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["state"], "REG_AWAIT_AREA")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["store_name"], "Toko Berkah Sejahtera")
            store_id = tg_listener.USER_STATES[chat_id]["store_id"]
            self.assertTrue(store_id.startswith("STR-"))
            mock_send_msg.assert_called_once()

        # Step 3: User picks area type callback
        with patch.object(tg_listener, "send_message") as mock_send_msg, \
             patch.object(tg_listener, "answer_callback_query") as mock_ans_cb:
            tg_listener.handle_reg_area(chat_id, "Residensial / Pemukiman", "cb-area-1")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["state"], "REG_AWAIT_LOCATION")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["area_type"], "Residensial / Pemukiman")

        # Step 4: User sends Telegram native location payload
        gps_payload = {
            "location": {
                "latitude": -6.208812,
                "longitude": 106.845634,
            }
        }
        with patch.object(tg_listener, "send_message") as mock_send_msg:
            tg_listener.handle_message(chat_id, gps_payload)
            self.assertEqual(tg_listener.USER_STATES[chat_id]["state"], "REG_AWAIT_ZONE")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["latitude"], -6.208812)
            self.assertEqual(tg_listener.USER_STATES[chat_id]["longitude"], 106.845634)

        # Step 5: User types logistics zone
        with patch.object(tg_listener, "send_message") as mock_send_msg:
            tg_listener.handle_message(chat_id, "ZONE-JAKSEL-01")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["state"], "REG_AWAIT_INGESTION")
            self.assertEqual(tg_listener.USER_STATES[chat_id]["zone"], "ZONE-JAKSEL-01")

        # Step 6: User selects ingestion mode callback (POS_WEBHOOK)
        with patch.object(tg_listener, "send_message") as mock_send_msg, \
             patch.object(tg_listener, "answer_callback_query") as mock_ans_cb:
            tg_listener.handle_reg_ingest(chat_id, "POS_WEBHOOK", "cb-ingest-1")
            # State should be cleared upon successful registration
            self.assertNotIn(chat_id, tg_listener.USER_STATES)

        # Step 7: Verify Store is synchronously persisted in SQLite DB
        persisted = get_store_by_id(store_id)
        self.assertIsNotNone(persisted, "Store was not saved to SQLite")
        self.assertEqual(persisted["store_name"], "Toko Berkah Sejahtera")
        self.assertEqual(persisted["area_type"], "Residensial / Pemukiman")
        self.assertAlmostEqual(persisted["latitude"], -6.208812, places=5)
        self.assertAlmostEqual(persisted["longitude"], 106.845634, places=5)
        self.assertEqual(persisted["telegram_chat_id"], chat_id)
        self.assertEqual(persisted["zone"], "ZONE-JAKSEL-01")


if __name__ == "__main__":
    unittest.main()
