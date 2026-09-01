"""Unit Tests for SAP S/4HANA OData Integration (PRD Section 11.9, 14.1 & 14.2)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.services.sap_service import SapIntegrationService

class TestSapIntegration(unittest.TestCase):

    def setUp(self):
        self.sap = SapIntegrationService()

    def test_oauth_token_retrieval_and_caching(self):
        """OAuth2 bearer token is generated and cached within validity window."""
        t1 = self.sap.get_access_token()
        t2 = self.sap.get_access_token()
        self.assertIsNotNone(t1)
        self.assertEqual(t1, t2)

    def test_pr_payload_builder(self):
        """Builds valid OData API_PURCHASEREQ_PROCESS_SRV payload."""
        payload = self.sap.build_pr_payload(
            sku_id="SKU-10023",
            sku_name="Roti Manis Cokelat",
            quantity=15,
            plant="1000",
            storage_location="STR-001"
        )
        self.assertEqual(payload.PurchaseRequisitionType, "NB")
        self.assertEqual(len(payload.PurchaseRequisitionItems), 1)
        item = payload.PurchaseRequisitionItems[0]
        self.assertEqual(item.Material, "SKU-10023")
        self.assertEqual(item.RequestedQuantity, 15)
        self.assertEqual(item.Plant, "1000")

    def test_create_pr_success_and_idempotency(self):
        """PR is created successfully and subsequent call with same request_id returns identical PR ID."""
        req_id = "REQ-SAP-IDEMPOTENT-001"
        payload = self.sap.build_pr_payload("SKU-10023", "Roti Manis Cokelat", 15)

        resp1 = self.sap.create_purchase_requisition(req_id, payload)
        self.assertTrue(resp1.success)
        self.assertIsNotNone(resp1.sap_pr_id)

        # Re-send with same request_id
        resp2 = self.sap.create_purchase_requisition(req_id, payload)
        self.assertTrue(resp2.success)
        self.assertEqual(resp1.sap_pr_id, resp2.sap_pr_id)

    def test_sap_downtime_error_handling(self):
        """When SAP returns 503 gateway error, service returns failed response without crashing."""
        self.sap._simulate_failure = True
        payload = self.sap.build_pr_payload("SKU-10023", "Roti Manis Cokelat", 15)
        resp = self.sap.create_purchase_requisition("REQ-FAIL-001", payload)

        self.assertFalse(resp.success)
        self.assertEqual(resp.status_code, 503)
        self.assertIn("Timeout", resp.error_message)

if __name__ == "__main__":
    unittest.main()
