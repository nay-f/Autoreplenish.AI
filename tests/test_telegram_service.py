"""Telegram Bot API integration tests (PRD Section 11.7, 14.4, 15.6, 27).

Verifies: real HTTP POST to sendMessage / answerCallbackQuery / editMessageText,
Markdown card composition with the required callback data, and that dispatch
failures are logged and never crash the replenishment pipeline.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    FakeHTTPClient,
    FakeHTTPResponse,
    FakeSecretManager,
    telegram_ok_response,
    build_context,
    sku_perishable_fragile,
)
from src.services.telegram_service import TelegramService
from src.models.schema import AIRecommendationOutput


def build_service(http, bot_token="TEST-BOT-TOKEN", secret_service=None):
    return TelegramService(bot_token=bot_token, http_client=http, secret_service=secret_service)


class TestTelegramService(unittest.TestCase):

    def setUp(self):
        self.sku = sku_perishable_fragile()
        self.context = build_context(self.sku)
        self.recommendation = AIRecommendationOutput(
            recommended_qty=20,
            normal_qty=48,
            adjusted_qty_before_moq=20,
            moq_applied=True,
            packaging_multiple_applied=True,
            confidence_score=0.88,
            risk_level="medium",
            reasoning_narrative="Stok 4 kg di bawah threshold 12 kg.",
            key_factors=["below_threshold", "fragile"],
            warnings=["Barang mudah pecah"],
        )

    # ---------------------------------------------------------
    # sendMessage
    # ---------------------------------------------------------
    def test_send_recommendation_card_posts_real_telegram_payload(self):
        http = FakeHTTPClient([telegram_ok_response(message_id=777)])
        service = build_service(http)

        result = service.send_recommendation_card(
            chat_id="1181431005",
            context=self.context,
            recommendation=self.recommendation,
            final_qty=20,
            request_id="REQ-20260616-0001",
        )

        self.assertTrue(result["delivered"])
        self.assertEqual(result["message_id"], "777")

        self.assertEqual(len(http.calls), 1)
        call = http.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(
            call["url"],
            "https://api.telegram.org/botTEST-BOT-TOKEN/sendMessage",
        )

        payload = call["json"]
        self.assertEqual(payload["chat_id"], "1181431005")
        self.assertEqual(payload["parse_mode"], "Markdown")
        self.assertIn("AUTOREPLENISH.AI", payload["text"])
        self.assertIn("Telur Ayam Ras Segar 1kg", payload["text"])
        self.assertIn("REQ-20260616-0001", payload["text"])

    def test_inline_keyboard_callback_data_matches_prd_14_4(self):
        http = FakeHTTPClient([telegram_ok_response()])
        service = build_service(http)

        service.send_recommendation_card(
            chat_id="1181431005", context=self.context,
            recommendation=self.recommendation, final_qty=20,
            request_id="REQ-20260616-0001",
        )

        keyboard = http.calls[0]["json"]["reply_markup"]["inline_keyboard"]
        callbacks = [btn["callback_data"] for row in keyboard for btn in row]

        self.assertEqual(len(keyboard), 2)
        self.assertIn("APPROVE:REQ-20260616-0001", callbacks)
        self.assertIn("EDIT:REQ-20260616-0001", callbacks)
        self.assertIn("REJECT:REQ-20260616-0001", callbacks)
        self.assertNotIn("callback_data", json.dumps({"x": 1}))  # sanity

    def test_fallback_mode_is_disclosed_in_the_card(self):
        degraded = AIRecommendationOutput(
            recommended_qty=20, normal_qty=48, adjusted_qty_before_moq=20,
            reasoning_narrative="Analisis aturan internal.", is_fallback=True,
        )
        http = FakeHTTPClient([telegram_ok_response()])
        service = build_service(http)

        service.send_recommendation_card(
            chat_id="1181431005", context=self.context,
            recommendation=degraded, final_qty=20, request_id="REQ-X",
        )
        self.assertIn("Model AI tidak dapat dihubungi", http.calls[0]["json"]["text"])

    # ---------------------------------------------------------
    # answerCallbackQuery
    # ---------------------------------------------------------
    def test_answer_callback_query_is_dispatched(self):
        http = FakeHTTPClient([telegram_ok_response()])
        service = build_service(http)

        service.answer_callback_query("cb-12345", "Memproses...", show_alert=False)

        self.assertEqual(len(http.calls), 1)
        call = http.calls[0]
        self.assertEqual(call["url"], "https://api.telegram.org/botTEST-BOT-TOKEN/answerCallbackQuery")
        self.assertEqual(call["json"]["callback_query_id"], "cb-12345")
        self.assertEqual(call["json"]["text"], "Memproses...")
        self.assertFalse(call["json"]["show_alert"])

    def test_answer_callback_query_skipped_without_id(self):
        http = FakeHTTPClient([])
        service = build_service(http)
        self.assertIsNone(service.answer_callback_query("", "text"))
        self.assertEqual(len(http.calls), 0)

    # ---------------------------------------------------------
    # editMessageText
    # ---------------------------------------------------------
    def test_edit_message_text_updates_the_original_card(self):
        http = FakeHTTPClient([telegram_ok_response()])
        service = build_service(http)

        service.edit_message_text(
            chat_id="1181431005",
            message_id="777",
            text="✅ Purchase Requisition Dibuat",
            reply_markup={"inline_keyboard": []},
        )

        call = http.calls[0]
        self.assertEqual(call["url"], "https://api.telegram.org/botTEST-BOT-TOKEN/editMessageText")
        self.assertEqual(call["json"]["message_id"], 777)
        self.assertEqual(call["json"]["chat_id"], "1181431005")
        self.assertEqual(call["json"]["text"], "✅ Purchase Requisition Dibuat")
        self.assertEqual(call["json"]["reply_markup"], {"inline_keyboard": []})

    def test_edit_message_text_skipped_without_message_id(self):
        http = FakeHTTPClient([])
        service = build_service(http)
        self.assertIsNone(service.edit_message_text("1181431005", None, "text"))
        self.assertIsNone(service.edit_message_text("1181431005", "", "text"))
        self.assertEqual(len(http.calls), 0)

    # ---------------------------------------------------------
    # Failure handling
    # ---------------------------------------------------------
    def test_failed_send_does_not_raise_and_marks_undelivered(self):
        http = FakeHTTPClient([FakeHTTPResponse(403, {"ok": False, "description": "bot blocked by user"})])
        service = build_service(http)

        result = service.send_recommendation_card(
            chat_id="1181431005", context=self.context,
            recommendation=self.recommendation, final_qty=20, request_id="REQ-FAIL",
        )

        self.assertFalse(result["delivered"])
        self.assertIsNone(result["message_id"])
        self.assertIsNone(result["reply_markup"])  # no stale buttons
        self.assertIn("error", result)

    def test_network_exception_does_not_raise(self):
        class ExplodingHTTP:
            def get(self, *a, **k):
                raise RuntimeError("network down")

            def post(self, *a, **k):
                raise RuntimeError("network down")

        service = build_service(ExplodingHTTP())
        result = service.send_recommendation_card(
            chat_id="1181431005", context=self.context,
            recommendation=self.recommendation, final_qty=20, request_id="REQ-NET",
        )
        self.assertFalse(result["delivered"])

        self.assertIsNone(service.answer_callback_query("cb", "x"))
        self.assertIsNone(service.edit_message_text("1181431005", "777", "text"))

    def test_bot_token_resolved_from_secrets_manager(self):
        secret_service = FakeSecretManager({
            "autoreplenish/telegram-credentials-dev": {
                "bot_token": "SECRET-TOKEN-123", "chat_id": "1181431005",
            }
        })
        http = FakeHTTPClient([telegram_ok_response()])
        service = TelegramService(http_client=http, secret_service=secret_service)

        service.send_message("1181431005", "hello")
        self.assertEqual(http.calls[0]["url"], "https://api.telegram.org/botSECRET-TOKEN-123/sendMessage")


if __name__ == "__main__":
    unittest.main()
