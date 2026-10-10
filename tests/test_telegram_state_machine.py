"""Telegram State Machine & Human-in-the-Loop tests (PRD Section 11.7, 11.8, 15.6).

Focused on the webhook processor: callback acknowledgement ordering, free-text
conversation flows, duplicate-click protection, expiry, and audit finalisation.
"""

import os
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    moto_dynamo_table,
    FakeHTTPClient,
    telegram_ok_response,
    sku_perishable_fragile,
    TEST_TABLE_NAME,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.sap_service import SapIntegrationService
from src.services.telegram_service import TelegramService
from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor, _verify_webhook_secret
from src.models.schema import TelegramStateRecord, AWAITING_QTY, AWAITING_REJECT_REASON


class TelegramStateMachineTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()
        cls.db = DynamoDBService(table_name=TEST_TABLE_NAME, client=cls.table)

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def setUp(self):
        for item in self.table.scan().get("Items", []):
            self.table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    def _dispatch(self, http=None):
        telegram = TelegramService(bot_token="T", http_client=http or FakeHTTPClient([]))
        return TelegramWebhookProcessor(self.db, telegram_service=telegram), telegram

    def _create_state(self, request_id="REQ-SM-0001", status="PENDING_APPROVAL"):
        now = datetime.now(timezone.utc)
        state = TelegramStateRecord(
            request_id=request_id,
            run_id="RUN-SM-0001",
            store_id="STR-ALMADINA-001",
            sku_id="SKU-ALM-003",
            recommended_qty=20,
            telegram_chat_id="1181431005",
            telegram_message_id="555",
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=4)).isoformat(),
            status=status,
        )
        self.db.put_telegram_state(state)
        return state


class TestCallbackHandling(TelegramStateMachineTestBase):

    def test_answer_callback_query_is_sent_first(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(5)])
        processor, _ = self._dispatch(http)
        self._create_state()

        processor.handle_callback_query("APPROVE:REQ-SM-0001", callback_query_id="cb-1")

        # The very first outbound Bot API call must be answerCallbackQuery.
        self.assertEqual(http.calls[0]["url"].split("/")[-1], "answerCallbackQuery")
        self.assertEqual(http.calls[0]["json"]["callback_query_id"], "cb-1")

    def test_edit_prompt_updates_card_and_waits_for_input(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(4)])
        processor, _ = self._dispatch(http)
        self._create_state()

        result = processor.handle_callback_query("EDIT:REQ-SM-0001", callback_query_id="cb-2")

        self.assertEqual(result["status"], "edit_prompt")
        state = self.db.get_telegram_state("REQ-SM-0001")
        self.assertEqual(state.awaiting_input, AWAITING_QTY)
        self.assertEqual(self.db.get_chat_pending_request("1181431005"), "REQ-SM-0001")

    def test_reject_prompt_waits_for_reason_input(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(4)])
        processor, _ = self._dispatch(http)
        self._create_state()
        result = processor.handle_callback_query("REJECT:REQ-SM-0001", callback_query_id="cb-3")
        self.assertEqual(result["status"], "reject_prompt")
        state = self.db.get_telegram_state("REQ-SM-0001")
        self.assertEqual(state.awaiting_input, AWAITING_REJECT_REASON)

    def test_free_text_qty_reply_completes_the_flow(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(6)])
        processor, _ = self._dispatch(http)
        self._create_state()
        self.db.put_sku(sku_perishable_fragile())

        processor.handle_callback_query("EDIT:REQ-SM-0001", callback_query_id="cb-2")
        result = processor.handle_update({"message": {
            "chat": {"id": 1181431005},
            "text": "40",
        }})

        self.assertEqual(result["status"], "success")
        self.assertEqual(self.db.get_telegram_state("REQ-SM-0001").final_qty, 40)
        # The pending pointer must be released once the conversation ends.
        self.assertIsNone(self.db.get_chat_pending_request("1181431005"))

    def test_non_numeric_qty_reply_is_rejected(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(6)])
        processor, _ = self._dispatch(http)
        self._create_state()

        processor.handle_callback_query("EDIT:REQ-SM-0001", callback_query_id="cb-2")
        result = processor.handle_update({"message": {"chat": {"id": 1181431005}, "text": "banyak"}})

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            self.db.get_telegram_state("REQ-SM-0001").awaiting_input, AWAITING_QTY
        )

    def test_free_text_rejection_reason_is_recorded(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(6)])
        processor, _ = self._dispatch(http)
        self._create_state()

        processor.handle_callback_query("REJECT:REQ-SM-0001", callback_query_id="cb-3")
        result = processor.handle_update({"message": {
            "chat": {"id": 1181431005},
            "text": "Toko tutup lebih awal karena ada acara desa",
        }})

        self.assertEqual(result["status"], "rejected")
        state = self.db.get_telegram_state("REQ-SM-0001")
        self.assertEqual(state.status, "REJECTED")
        self.assertIn("acara desa", state.rejection_reason)

    def test_duplicate_approve_is_blocked(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(8)])
        processor, _ = self._dispatch(http)
        self._create_state()

        first = processor.handle_callback_query("APPROVE:REQ-SM-0001", callback_query_id="cb-1")
        second = processor.handle_callback_query("APPROVE:REQ-SM-0001", callback_query_id="cb-1")

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "already_processed")
        self.assertEqual(len(self.db.list_sap_transactions()), 1)

    def test_expired_request_rejects_approval(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(5)])
        processor, _ = self._dispatch(http)
        state = self._create_state()
        state.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        self.db.put_telegram_state(state)

        result = processor.handle_callback_query("APPROVE:REQ-SM-0001", callback_query_id="cb-1")
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(self.db.get_telegram_state("REQ-SM-0001").status, "TIMEOUT")
        self.assertIsNone(self.db.get_sap_transaction("REQ-SM-0001"))

    def test_unknown_request_is_handled_without_error(self):
        processor, _ = self._dispatch(FakeHTTPClient([telegram_ok_response()]))
        result = processor.handle_callback_query("APPROVE:REQ-NOPE", callback_query_id="cb")
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["message"])

    def test_malformed_callback_data(self):
        processor, _ = self._dispatch(FakeHTTPClient([telegram_ok_response()]))
        result = processor.handle_callback_query("GARBAGE", callback_query_id="cb")
        self.assertEqual(result["status"], "error")

    def test_unknown_action(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(3)])
        processor, _ = self._dispatch(http)
        self._create_state()
        result = processor.handle_callback_query("MAYBE:REQ-SM-0001", callback_query_id="cb")
        self.assertEqual(result["status"], "error")
        self.assertIn("tidak dikenal", result["message"])

    def test_chat_pointer_ttl_release_after_rejection(self):
        http = FakeHTTPClient([telegram_ok_response() for _ in range(6)])
        processor, _ = self._dispatch(http)
        self._create_state()
        processor.handle_callback_query("REJECT:REQ-SM-0001", callback_query_id="cb-3")
        processor.handle_update({"message": {"chat": {"id": 1181431005}, "text": "Alasan apa pun"}})
        self.assertIsNone(self.db.get_chat_pending_request("1181431005"))


class TestWebhookLambdaHandler(TelegramStateMachineTestBase):

    def test_lambda_handler_processes_callback_update(self):
        self._create_state()
        telegram = TelegramService(bot_token="T", http_client=FakeHTTPClient([telegram_ok_response() for _ in range(6)]))
        processor_sap = SapIntegrationService(db_service=self.db)

        import src.handlers.telegram_webhook_handler as handler_module
        with unittest.mock.patch.object(handler_module, "DynamoDBService", lambda: self.db), \
             unittest.mock.patch.object(handler_module, "TelegramService", lambda *a, **k: telegram), \
             unittest.mock.patch.object(handler_module, "SapIntegrationService", lambda *a, **k: processor_sap), \
             unittest.mock.patch.object(handler_module, "_webhook_secret", lambda: ""):
            response = handler_module.lambda_handler({
                "body": json.dumps({
                    "callback_query": {"id": "cb-9", "data": "APPROVE:REQ-SM-0001",
                                       "from": {"id": 1181431005}}
                })
            }, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["actor_user_id"], "1181431005")
        self.assertEqual(self.db.get_telegram_state("REQ-SM-0001").status, "PR_CREATED")

    def test_lambda_handler_rejects_bad_webhook_secret(self):
        import src.handlers.telegram_webhook_handler as handler_module
        with unittest.mock.patch.object(handler_module, "_webhook_secret", lambda: "expected-secret"):
            response = handler_module.lambda_handler({
                "headers": {"X-Telegram-Bot-Api-Secret-Token": "wrong"},
                "body": json.dumps({"callback_query": {"id": "x", "data": "APPROVE:y"}}),
            }, None)
        self.assertEqual(response["statusCode"], 403)

    def test_webhook_secret_verification_helpers(self):
        self.assertTrue(_verify_webhook_secret({"headers": {}}, ""))
        self.assertTrue(_verify_webhook_secret(
            {"headers": {"X-Telegram-Bot-Api-Secret-Token": "s"}}, "s"))
        self.assertTrue(_verify_webhook_secret(
            {"headers": {"x-telegram-bot-api-secret-token": "s"}}, "s"))
        self.assertFalse(_verify_webhook_secret(
            {"headers": {"X-Telegram-Bot-Api-Secret-Token": "nope"}}, "s"))

    def test_lambda_handler_ignores_unactionable_update(self):
        import src.handlers.telegram_webhook_handler as handler_module
        with unittest.mock.patch.object(handler_module, "_webhook_secret", lambda: ""):
            response = handler_module.lambda_handler({"body": json.dumps({})}, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("ignored", response["body"])


if __name__ == "__main__":
    unittest.main()
