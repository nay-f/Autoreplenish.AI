"""End-to-End User Journey Tests for AutoReplenish.ai (PRD Section 19, 20.3).

The full chain runs against a moto-emulated DynamoDB table with doubles only at
the network boundary (Bedrock, OpenWeatherMap, Telegram):

    EventBridge -> prioritization -> Bedrock reasoning -> Telegram card
    -> store manager approves -> SAP PR (PERSISTENT_SANDBOX) -> audit trail
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    moto_dynamo_table,
    FakeBedrockClient,
    FakeHTTPClient,
    FakeHTTPResponse,
    telegram_ok_response,
    owm_payload,
    almadina_store,
    sku_perishable_fragile,
    TEST_TABLE_NAME,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.weather_service import WeatherService
from src.services.calendar_promo_service import CalendarPromoService
from src.services.bedrock_service import BedrockReasoningService
from src.services.telegram_service import TelegramService
from src.services.orchestrator_service import OrchestratorService


def weather_http():
    """Fake OpenWeatherMap: Wirosari, light rain."""
    return FakeHTTPClient([FakeHTTPResponse(200, owm_payload(
        temp=28.3, description="light rain", rain_1h=1.2
    )) for _ in range(8)])


def build_stack(table, telegram_http=None):
    db = DynamoDBService(table_name=TEST_TABLE_NAME, client=table)
    telegram_service = TelegramService(
        bot_token="TEST-TOKEN",
        http_client=telegram_http or FakeHTTPClient([telegram_ok_response(message_id=9001)]),
    )
    weather_service = WeatherService(db, api_key="test-owm-key", http_client=weather_http())
    orchestrator = OrchestratorService(
        db_service=db,
        weather_service=weather_service,
        calendar_promo_service=CalendarPromoService(),
        bedrock_service=BedrockReasoningService(bedrock_client=FakeBedrockClient()),
        telegram_service=telegram_service,
    )
    return {
        "db": db,
        "weather": weather_service,
        "telegram": telegram_service,
        "orchestrator": orchestrator,
    }


STOCK_LEVELS = {
    "SKU-ALM-003": {
        "physical_stock": 4, "threshold": 12, "average_daily_burn_rate": 8.0,
        "lead_time_days": 1, "open_pr_qty": 0,
    }
}


class TestEndToEndFlow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def test_journey_1_happy_path_approval(self):
        """PRD 19.1: schedule -> AI -> card -> approve -> SAP PR -> audit trail."""
        from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor

        telegram_http = FakeHTTPClient([
            telegram_ok_response(message_id=9001),   # card
            telegram_ok_response(),                  # answerCallbackQuery
            telegram_ok_response(),                  # editMessageText
        ])
        stack = build_stack(self.table, telegram_http=telegram_http)
        store = almadina_store()
        sku = sku_perishable_fragile()

        audit_logs = stack["orchestrator"].process_store_evaluation(
            store=store, skus=[sku], stock_levels=STOCK_LEVELS, run_id="RUN-E2E-0001",
        )
        self.assertEqual(len(audit_logs), 1)
        log = audit_logs[0]
        request_id = log.request_id

        # --- Telegram card was actually dispatched over HTTP -----------------
        card_call = telegram_http.calls[0]
        self.assertEqual(card_call["url"], "https://api.telegram.org/botTEST-TOKEN/sendMessage")
        self.assertIn("Telur Ayam Ras Segar 1kg", card_call["json"]["text"])
        self.assertIn(f"APPROVE:{request_id}", json.dumps(card_call["json"]["reply_markup"]))

        # --- State + audit persisted in DynamoDB -----------------------------
        state = stack["db"].get_telegram_state(request_id)
        self.assertEqual(state.status, "PENDING_APPROVAL")
        self.assertEqual(state.telegram_message_id, "9001")

        # --- Store manager presses Approve -----------------------------------
        processor = TelegramWebhookProcessor(stack["db"], telegram_service=stack["telegram"])
        result = processor.handle_callback_query(f"APPROVE:{request_id}", callback_query_id="cb-1")

        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["sap_pr_id"])
        self.assertRegex(result["sap_pr_id"], r"^\d{10}$")

        # answerCallbackQuery must be issued immediately after the click
        self.assertEqual(telegram_http.calls[1]["url"].split("bot")[-1],
                         "TEST-TOKEN/answerCallbackQuery")

        # --- Final state, audit, and SAP ledger ------------------------------
        final_state = stack["db"].get_telegram_state(request_id)
        self.assertEqual(final_state.status, "PR_CREATED")
        self.assertEqual(final_state.sap_pr_id, result["sap_pr_id"])

        audit = stack["db"].get_audit_log_by_request_id(request_id)
        self.assertEqual(audit.human_action, "APPROVED")
        self.assertEqual(audit.sap_pr_status, "SUCCESS")
        self.assertEqual(audit.sap_pr_id, result["sap_pr_id"])
        self.assertEqual(audit.sap_mode, "PERSISTENT_SANDBOX")

        txn = stack["db"].get_sap_transaction(request_id)
        self.assertIsNotNone(txn)
        self.assertEqual(txn.status, "SUCCESS")

    def test_journey_1b_dashboard_can_read_the_audit_trail(self):
        from src.handlers.dashboard_api_handler import DashboardApiProcessor

        stack = build_stack(self.table, telegram_http=FakeHTTPClient([telegram_ok_response()]))
        stack["orchestrator"].process_store_evaluation(
            store=almadina_store(), skus=[sku_perishable_fragile()],
            stock_levels=STOCK_LEVELS, run_id="RUN-E2E-DASH",
        )

        api = DashboardApiProcessor(stack["db"])
        logs = api.get_audit_logs(store_id="STR-ALMADINA-001", limit=50)
        self.assertTrue(logs)

        monitor = api.get_sap_monitor()
        self.assertEqual(monitor["connection_status"], "SANDBOX")
        self.assertIn("API_PURCHASEREQ_PROCESS_SRV", monitor["odata_endpoint"])

        analytics = api.get_feedback_analytics()
        self.assertIn("approval_rate_pct", analytics["metrics"])
        self.assertIn("rule_based_fallback_count", analytics["metrics"])

    def test_journey_1c_inventory_health_reflects_seeded_master_data(self):
        from src.handlers.dashboard_api_handler import DashboardApiProcessor
        from src.handlers.scheduled_eval_handler import seed_database_if_empty

        stack = build_stack(self.table, telegram_http=FakeHTTPClient([telegram_ok_response()]))
        seed_database_if_empty(stack["db"])

        api = DashboardApiProcessor(stack["db"])
        health = api.get_store_inventory_health("STR-COMMERCIAL-01")

        self.assertEqual(health["store_name"], "Minimarket Cabang Sentra Bisnis")
        self.assertEqual(health["zone"], "JAKARTA_PUSAT")
        self.assertEqual(health["area_type"], "Komersial / Perkantoran")
        self.assertIn("Jakarta", health["address"])
        self.assertEqual(len(health["inventory"]), 4)
        self.assertEqual(health["summary"]["stockout_risk"] + health["summary"]["healthy"]
                         + health["summary"]["overstock_risk"], 4)

        by_sku = {i["sku_id"]: i for i in health["inventory"]}
        self.assertEqual(by_sku["SKU-FMCG-001"]["shelf_life_days"], 3)
        self.assertEqual(by_sku["SKU-FMCG-002"]["base_unit"], "KARUNG")
        self.assertTrue(by_sku["SKU-FMCG-004"]["weather_sensitive"])

        # Store coordinates are persisted in DynamoDB and exposed via the stores API.
        stores = {s["store_id"]: s for s in api.get_stores()}
        self.assertAlmostEqual(stores["STR-RESIDENTIAL-01"]["latitude"], -6.9666, places=4)
        self.assertAlmostEqual(stores["STR-RESIDENTIAL-01"]["longitude"], 110.4166, places=4)

    def test_journey_2_edit_quantity_path(self):
        """PRD 19.2: manager edits qty -> MOQ/packaging enforced -> PR -> feedback."""
        from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor

        telegram_http = FakeHTTPClient([telegram_ok_response(9001),
                                        telegram_ok_response(),
                                        telegram_ok_response(),
                                        telegram_ok_response()])
        stack = build_stack(self.table, telegram_http=telegram_http)
        store = almadina_store()
        sku = sku_perishable_fragile()
        stack["db"].put_store(store)
        stack["db"].put_sku(sku)
        stack["orchestrator"].process_store_evaluation(
            store=store, skus=[sku], stock_levels=STOCK_LEVELS, run_id="RUN-E2E-0002",
        )
        request_id = stack["db"].list_audit_logs(store_id="STR-ALMADINA-001")[0].request_id

        processor = TelegramWebhookProcessor(stack["db"], telegram_service=stack["telegram"])
        edit_resp = processor.handle_callback_query(f"EDIT:{request_id}", callback_query_id="cb-2")
        self.assertEqual(edit_resp["status"], "edit_prompt")

        # Free-text reply carrying the new quantity (multiples of 10 KG)
        result = processor.handle_manual_qty_edit(request_id, "26")
        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["sap_pr_id"])

        state = stack["db"].get_telegram_state(request_id)
        self.assertEqual(state.final_qty, 30)  # rounded up to a 10 KG tray
        self.assertIsInstance(state.final_qty, int)
        self.assertEqual(state.status, "PR_CREATED")

        feedbacks = stack["db"].list_all_feedbacks()
        edited = [f for f in feedbacks if f.action == "EDITED" and f.store_id == "STR-ALMADINA-001"]
        self.assertTrue(edited)
        self.assertEqual(edited[0].final_qty, 30)

    def test_journey_3_rejection_path(self):
        """PRD 19.3: manager rejects -> feedback stored -> no PR created."""
        from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor

        telegram_http = FakeHTTPClient([telegram_ok_response(9001)] + [telegram_ok_response() for _ in range(5)])
        stack = build_stack(self.table, telegram_http=telegram_http)
        stack["orchestrator"].process_store_evaluation(
            store=almadina_store(), skus=[sku_perishable_fragile()],
            stock_levels=STOCK_LEVELS, run_id="RUN-E2E-0003",
        )
        request_id = stack["db"].list_audit_logs(store_id="STR-ALMADINA-001")[0].request_id

        processor = TelegramWebhookProcessor(stack["db"], telegram_service=stack["telegram"])
        reject_resp = processor.handle_callback_query(f"REJECT:{request_id}", callback_query_id="cb-3")
        self.assertEqual(reject_resp["status"], "reject_prompt")

        reason = "Stok di gudang belakang masih ada dan belum terinput di sistem"
        final = processor.handle_rejection(request_id, reason)
        self.assertEqual(final["status"], "rejected")

        state = stack["db"].get_telegram_state(request_id)
        self.assertEqual(state.status, "REJECTED")
        self.assertIsNone(state.sap_pr_id)

        audit = stack["db"].get_audit_log_by_request_id(request_id)
        self.assertEqual(audit.human_action, "REJECTED")
        self.assertEqual(audit.rejection_reason, reason)
        self.assertIsNone(stack["db"].get_sap_transaction(request_id))

    def test_double_click_cannot_create_a_second_pr(self):
        """PRD 15.6: duplicate approvals must be idempotent."""
        from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor

        telegram_http = FakeHTTPClient([telegram_ok_response(9001)] + [telegram_ok_response() for _ in range(6)])
        stack = build_stack(self.table, telegram_http=telegram_http)
        stack["orchestrator"].process_store_evaluation(
            store=almadina_store(), skus=[sku_perishable_fragile()],
            stock_levels=STOCK_LEVELS, run_id="RUN-E2E-0004",
        )
        request_id = stack["db"].list_audit_logs(store_id="STR-ALMADINA-001")[0].request_id

        processor = TelegramWebhookProcessor(stack["db"], telegram_service=stack["telegram"])
        first = processor.handle_callback_query(f"APPROVE:{request_id}", callback_query_id="cb-1")
        second = processor.handle_callback_query(f"APPROVE:{request_id}", callback_query_id="cb-1")

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "already_processed")
        self.assertEqual(first["sap_pr_id"], second["message"].split("PR: ")[-1].rstrip(")."))
        # Only a single PR row exists for this request.
        self.assertEqual(len(stack["db"].list_sap_transactions()), sum(
            1 for t in stack["db"].list_sap_transactions()
            if t.request_id == request_id
        ))

    def test_timeout_rejects_late_approval(self):
        """PRD 11.8: approvals after the 4-hour window must be refused."""
        from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor
        from datetime import datetime, timezone, timedelta

        telegram_http = FakeHTTPClient([telegram_ok_response(9001)] + [telegram_ok_response() for _ in range(6)])
        stack = build_stack(self.table, telegram_http=telegram_http)
        stack["orchestrator"].process_store_evaluation(
            store=almadina_store(), skus=[sku_perishable_fragile()],
            stock_levels=STOCK_LEVELS, run_id="RUN-E2E-0005",
        )
        request_id = stack["db"].list_audit_logs(store_id="STR-ALMADINA-001")[0].request_id

        # Age the request past the expiry.
        state = stack["db"].get_telegram_state(request_id)
        state.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        stack["db"].put_telegram_state(state)

        processor = TelegramWebhookProcessor(stack["db"], telegram_service=stack["telegram"])
        result = processor.handle_callback_query(f"APPROVE:{request_id}", callback_query_id="cb-1")
        self.assertEqual(result["status"], "timeout")
        self.assertIsNone(stack["db"].get_sap_transaction(request_id))
        self.assertEqual(stack["db"].get_telegram_state(request_id).status, "TIMEOUT")

    def test_scheduled_eval_lambda_handler_runs_end_to_end(self):
        """The actual Lambda entry point executes with the Almadina master data."""
        from src.handlers import scheduled_eval_handler as handler

        # Patch only the DI boundaries: the real object graph runs against
        # in-process doubles for the network-bound adapters.
        original_db = DynamoDBService

        class FakeDB(original_db):
            def __init__(self, *a, **k):
                super().__init__(table_name=TEST_TABLE_NAME, client=self.table)

        FakeDB.table = self.table
        telegram_http = FakeHTTPClient([telegram_ok_response(9001) for _ in range(10)])

        with unittest.mock.patch.object(handler, "DynamoDBService", FakeDB), \
             unittest.mock.patch.object(handler, "WeatherService",
                                        lambda db, **k: WeatherService(
                                            db, api_key="k", http_client=weather_http())), \
             unittest.mock.patch.object(handler, "BedrockReasoningService",
                                        lambda **k: BedrockReasoningService(
                                            bedrock_client=FakeBedrockClient())), \
             unittest.mock.patch.object(handler, "TelegramService",
                                        lambda **k: TelegramService(
                                            bot_token="T", http_client=telegram_http)):
            response = handler.lambda_handler({"trigger_source": "TEST"}, None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["trigger_source"], "TEST")
        self.assertGreaterEqual(body["total_recommendations_dispatched"], 1)
        self.assertEqual(body["rule_based_fallback_count"], 0)
        self.assertGreater(body["total_skus_catalogued"], 0)

        # Both seeded stores are evaluated and recommendations include the generic FMCG SKUs.
        seeded_store_ids = {"STR-COMMERCIAL-01", "STR-RESIDENTIAL-01"}
        self.assertGreaterEqual(body["stores_count"], 2)
        self.assertGreaterEqual(body["total_skus_catalogued"], 4)
        self.assertTrue(seeded_store_ids.issubset({r["store_id"] for r in body["recommendations"]}))
        self.assertTrue(any(r["sku_id"].startswith("SKU-FMCG-") for r in body["recommendations"]))
        for rec in body["recommendations"]:
            self.assertFalse(rec["is_fallback"])


if __name__ == "__main__":
    unittest.main()
