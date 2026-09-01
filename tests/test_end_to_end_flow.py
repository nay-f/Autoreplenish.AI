"""End-to-End User Journey Tests for AutoReplenish.ai (PRD Section 19 & 20.3)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from conftest import create_test_orchestrator, get_test_store, get_test_sku_perishable
from src.handlers.telegram_webhook_handler import TelegramWebhookProcessor

class TestEndToEndFlow(unittest.TestCase):

    def setUp(self):
        self.services = create_test_orchestrator()
        self.orchestrator = self.services["orchestrator"]
        self.db = self.services["db"]
        self.sap = self.services["sap"]
        self.store = get_test_store()
        self.sku = get_test_sku_perishable()
        self.webhook_processor = TelegramWebhookProcessor(self.db, self.sap)

    def test_journey_1_happy_path_approval(self):
        """
        User Journey 19.1:
        EventBridge scheduled run -> Prioritization -> Bedrock conservative reasoning ->
        Telegram card sent -> Store Manager approves -> SAP PR created -> Full Audit Trace saved.
        """
        # 1. Setup scenario
        stock_levels = {
            self.sku.sku_id: {
                "physical_stock": 12,
                "threshold": 20,
                "average_daily_burn_rate": 25.0,
                "lead_time_days": 2,
                "open_pr_qty": 0
            }
        }

        # 2. Run Store Evaluation
        run_id = "RUN-20260901-0500"
        audit_logs = self.orchestrator.process_store_evaluation(
            store=self.store,
            skus=[self.sku],
            stock_levels=stock_levels,
            run_id=run_id
        )
        self.assertEqual(len(audit_logs), 1)
        log = audit_logs[0]
        request_id = log.request_id

        # Verify AI recommendation
        self.assertGreater(log.final_recommended_qty, 0)
        self.assertEqual(log.prompt_version, "v1.0")
        self.assertIn("below_threshold", log.key_factors)
        self.assertEqual(log.sap_pr_status, "PENDING")

        # 3. Store Manager approves via Telegram
        telegram_resp = self.webhook_processor.handle_callback_query(f"APPROVE:{request_id}")
        self.assertEqual(telegram_resp["status"], "success")
        self.assertIsNotNone(telegram_resp["sap_pr_id"])

        # 4. Verify Final State and Audit Log
        final_state = self.db.get_telegram_state(request_id)
        self.assertEqual(final_state.status, "PR_CREATED")
        self.assertEqual(final_state.sap_pr_id, telegram_resp["sap_pr_id"])

        final_audit = self.db.get_audit_log_by_request_id(request_id)
        self.assertEqual(final_audit.human_action, "APPROVED")
        self.assertEqual(final_audit.sap_pr_status, "SUCCESS")
        self.assertEqual(final_audit.sap_pr_id, telegram_resp["sap_pr_id"])

    def test_journey_2_edit_quantity_path(self):
        """
        User Journey 19.2:
        Store Manager edits quantity -> SAP PR created with edited qty -> Feedback logged.
        """
        stock_levels = {
            self.sku.sku_id: {
                "physical_stock": 10,
                "threshold": 20,
                "average_daily_burn_rate": 20.0,
                "lead_time_days": 2
            }
        }
        audit_logs = self.orchestrator.process_store_evaluation(
            store=self.store,
            skus=[self.sku],
            stock_levels=stock_levels
        )
        request_id = audit_logs[0].request_id

        # Store manager edits quantity to 24 pcs
        edit_resp = self.webhook_processor.handle_manual_qty_edit(request_id, new_qty=24)
        self.assertEqual(edit_resp["status"], "success")

        # Verify edited quantity in state and audit log
        state = self.db.get_telegram_state(request_id)
        self.assertEqual(state.final_qty, 24)

        audit = self.db.get_audit_log_by_request_id(request_id)
        self.assertEqual(audit.human_final_qty, 24)

        # Verify feedback entry
        feedbacks = self.db.list_recent_feedback(self.store.store_id, self.sku.sku_id)
        self.assertGreaterEqual(len(feedbacks), 1)
        self.assertEqual(feedbacks[0].action, "EDITED")

    def test_journey_3_rejection_path(self):
        """
        User Journey 19.3:
        Store Manager rejects recommendation with reason -> PR canceled -> Feedback recorded.
        """
        stock_levels = {
            self.sku.sku_id: {
                "physical_stock": 10,
                "threshold": 20,
                "average_daily_burn_rate": 20.0,
                "lead_time_days": 2
            }
        }
        audit_logs = self.orchestrator.process_store_evaluation(
            store=self.store,
            skus=[self.sku],
            stock_levels=stock_levels
        )
        request_id = audit_logs[0].request_id

        # Reject
        reason_text = "Stok di display masih penuh karena baru ditata ulang"
        reject_resp = self.webhook_processor.handle_rejection(request_id, reason_text)
        self.assertEqual(reject_resp["status"], "rejected")

        # Verify no PR in SAP and feedback saved
        state = self.db.get_telegram_state(request_id)
        self.assertEqual(state.status, "REJECTED")
        self.assertIsNone(state.sap_pr_id)

        audit = self.db.get_audit_log_by_request_id(request_id)
        self.assertEqual(audit.human_action, "REJECTED")
        self.assertEqual(audit.rejection_reason, reason_text)

if __name__ == "__main__":
    unittest.main()
