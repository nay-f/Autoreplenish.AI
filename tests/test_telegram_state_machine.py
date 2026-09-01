"""Unit Tests for Telegram State Machine and Idempotency (PRD Section 11.8 & 15.6)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from datetime import datetime, timezone, timedelta
from src.services.dynamodb_service import DynamoDBService
from src.services.sap_service import SapIntegrationService
from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor
from src.models.schema import TelegramStateRecord, SKUProfile

class TestTelegramStateMachine(unittest.TestCase):

    def setUp(self):
        self.db = DynamoDBService()
        self.sap = SapIntegrationService()
        self.processor = TelegramWebhookProcessor(self.db, self.sap)

        # Register sample SKU
        self.db.put_sku(SKUProfile(
            sku_id="SKU-10023",
            sku_name="Roti Manis Cokelat",
            category="Perishable",
            moq=12,
            packaging_multiple=12
        ))

        # Create sample Telegram pending state
        self.request_id = "REQ-TEST-001"
        now_dt = datetime.now(timezone.utc)
        self.state = TelegramStateRecord(
            PK=f"REQ#{self.request_id}",
            SK="STATE",
            request_id=self.request_id,
            run_id="RUN-TEST-001",
            store_id="STR-001",
            sku_id="SKU-10023",
            recommended_qty=15,
            status="PENDING_APPROVAL",
            telegram_chat_id="chat_001",
            created_at=now_dt.isoformat(),
            expires_at=(now_dt + timedelta(hours=4)).isoformat()
        )
        self.db.put_telegram_state(self.state)

    def test_approve_creates_sap_pr(self):
        """Approve transition creates SAP PR and updates state to PR_CREATED."""
        res = self.processor.handle_callback_query(f"APPROVE:{self.request_id}")
        self.assertEqual(res["status"], "success")
        self.assertIn("PR-", res["sap_pr_id"])

        updated_state = self.db.get_telegram_state(self.request_id)
        self.assertEqual(updated_state.status, "PR_CREATED")
        self.assertEqual(updated_state.sap_pr_id, res["sap_pr_id"])

    def test_duplicate_click_prevention(self):
        """Duplicate approve clicks return already_processed without creating second PR."""
        # First click
        res1 = self.processor.handle_callback_query(f"APPROVE:{self.request_id}")
        self.assertEqual(res1["status"], "success")

        # Second click
        res2 = self.processor.handle_callback_query(f"APPROVE:{self.request_id}")
        self.assertEqual(res2["status"], "already_processed")

    def test_rejection_stores_feedback_and_cancels_pr(self):
        """Reject callback stores feedback reason and sets state to REJECTED."""
        res = self.processor.handle_rejection(self.request_id, "Stok fisik di toko masih mencukupi")
        self.assertEqual(res["status"], "rejected")

        updated_state = self.db.get_telegram_state(self.request_id)
        self.assertEqual(updated_state.status, "REJECTED")

        # Verify feedback in DynamoDB
        feedbacks = self.db.list_recent_feedback("STR-001", "SKU-10023")
        self.assertEqual(len(feedbacks), 1)
        self.assertEqual(feedbacks[0].reason, "Stok fisik di toko masih mencukupi")

    def test_manual_qty_edit_flow(self):
        """Edit qty validates multiples and executes PR with adjusted qty."""
        res = self.processor.handle_manual_qty_edit(self.request_id, new_qty=24)
        self.assertEqual(res["status"], "success")

        updated_state = self.db.get_telegram_state(self.request_id)
        self.assertEqual(updated_state.final_qty, 24)

    def test_timeout_expiration_blocks_action(self):
        """Expired state (>4h) transitions to TIMEOUT and blocks PR creation."""
        expired_req_id = "REQ-EXPIRED-001"
        past_dt = datetime.now(timezone.utc) - timedelta(hours=5)
        expired_state = TelegramStateRecord(
            PK=f"REQ#{expired_req_id}",
            SK="STATE",
            request_id=expired_req_id,
            run_id="RUN-TEST-001",
            store_id="STR-001",
            sku_id="SKU-10023",
            recommended_qty=15,
            status="PENDING_APPROVAL",
            telegram_chat_id="chat_001",
            created_at=(past_dt - timedelta(hours=1)).isoformat(),
            expires_at=past_dt.isoformat()
        )
        self.db.put_telegram_state(expired_state)

        res = self.processor.handle_callback_query(f"APPROVE:{expired_req_id}")
        self.assertEqual(res["status"], "timeout")

        final_state = self.db.get_telegram_state(expired_req_id)
        self.assertEqual(final_state.status, "TIMEOUT")

if __name__ == "__main__":
    unittest.main()
