"""Unit and Integration Tests for POS Ingestion Handler.

Verifies:
1. POST /api/v1/ingest/pos/{store_id} validates X-POS-Secret-Key header.
2. Rejection with 401 when header is missing or incorrect.
3. Successful ingestion updates physical stock and daily sales (burn rate).
4. Subsequent inventory queries reflect the freshly synced closing shift numbers.
"""

import os
import sys
import json
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
DEMO_DIR = os.path.join(BASE_DIR, "demo")
for p in [BASE_DIR, BACKEND_DIR, DEMO_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.handlers.dashboard_api_handler import DashboardApiProcessor, lambda_handler
from demo.services.local_db import (
    init_db,
    get_inventory,
    get_store_settings,
    update_inventory_stock,
)
import importlib
api_module = importlib.import_module("demo.scripts.05_dashboard_api")
fastapi_app = getattr(api_module, "app")
from fastapi.testclient import TestClient


class TestPosIngestion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(fastapi_app)

    @patch("src.handlers.dashboard_api_handler.DynamoDBService")
    def test_backend_lambda_handler_pos_ingestion_success(self, mock_dynamo_cls):
        mock_db = MagicMock()
        mock_store = MagicMock()
        mock_store.store_id = "STR-COMMERCIAL-01"
        mock_store.store_name = "Minimarket Cabang Sentra Bisnis"
        mock_store.ingestion_config.webhook_secret = "sec_str_commercial_01_live"
        mock_db.get_store.return_value = mock_store
        mock_dynamo_cls.return_value = mock_db

        event = {
            "path": "/api/v1/ingest/pos/STR-COMMERCIAL-01",
            "requestContext": {"http": {"method": "POST"}},
            "headers": {"x-pos-secret-key": "sec_str_commercial_01_live"},
            "body": json.dumps({
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
            })
        }
        resp = lambda_handler(event, None)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["items_updated"], 2)
        self.assertIn("Inventory synced successfully", body["message"])

    @patch("src.handlers.dashboard_api_handler.DynamoDBService")
    def test_backend_lambda_handler_pos_ingestion_unauthorized(self, mock_dynamo_cls):
        mock_db = MagicMock()
        mock_store = MagicMock()
        mock_store.store_id = "STR-COMMERCIAL-01"
        mock_store.ingestion_config.webhook_secret = "secret-123"
        mock_db.get_store.return_value = mock_store
        mock_dynamo_cls.return_value = mock_db

        event = {
            "path": "/api/v1/ingest/pos/STR-COMMERCIAL-01",
            "requestContext": {"http": {"method": "POST"}},
            "headers": {"x-pos-secret-key": "wrong-secret-key"},
            "body": json.dumps({
                "store_id": "STR-COMMERCIAL-01",
                "inventory": []
            })
        }
        resp = lambda_handler(event, None)
        self.assertEqual(resp["statusCode"], 401)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "UNAUTHORIZED")

    def test_fastapi_pos_ingestion_endpoint_success(self):
        payload = {
            "store_id": "STR-COMMERCIAL-01",
            "timestamp": "2026-10-10T21:00:00Z",
            "sync_type": "CLOSING_SHIFT",
            "inventory": [
                {
                    "sku_id": "SKU-FMCG-001",
                    "current_physical_stock": 15,
                    "daily_sales_qty": 35
                },
                {
                    "sku_id": "SKU-FMCG-002",
                    "current_physical_stock": 8,
                    "daily_sales_qty": 12
                }
            ]
        }
        headers = {"X-POS-Secret-Key": "sec_str_commercial_01_live"}
        response = self.client.post("/api/v1/ingest/pos/STR-COMMERCIAL-01", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["items_updated"], 2)

        # Verify SQLite inventory was updated
        inv_item = get_inventory("STR-COMMERCIAL-01", "SKU-FMCG-001")
        self.assertIsNotNone(inv_item)
        self.assertEqual(inv_item["physical_stock"], 15)
        self.assertEqual(inv_item["average_daily_burn_rate"], 35)

    def test_fastapi_pos_ingestion_endpoint_unauthorized(self):
        payload = {"inventory": []}
        # Bad secret
        res1 = self.client.post("/api/v1/ingest/pos/STR-COMMERCIAL-01", json=payload, headers={"X-POS-Secret-Key": "invalid-key"})
        self.assertEqual(res1.status_code, 401)

        # Missing header
        res2 = self.client.post("/api/v1/ingest/pos/STR-COMMERCIAL-01", json=payload)
        self.assertEqual(res2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
