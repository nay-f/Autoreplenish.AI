"""SAP S/4HANA dual-mode integration tests (PRD Section 11.9, 14.1, 14.2).

Covers:
- PERSISTENT_SANDBOX (no credentials): SAP-accurate OData response, PR ledger
  written to DynamoDB, idempotency SURVIVING cold starts (fresh service object).
- LIVE mode: OAuth2 client-credentials token flow, X-CSRF-Token handshake,
  and the deep-insert POST to API_PURCHASEREQ_PROCESS_SRV.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import (
    moto_dynamo_table,
    FakeHTTPClient,
    FakeHTTPResponse,
    FakeSecretManager,
    make_pr_payload,
    TEST_TABLE_NAME,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.sap_service import SapIntegrationService, MODE_LIVE, MODE_SANDBOX
from src.config import SAP_SECRET_NAME

LIVE_CREDENTIALS = {
    "client_id": "AUTOREPLENISH_CLIENT",
    "client_secret": "s4h-secret",
    "token_url": "https://s4h.example.com/sap/bc/sec/oauth2/token",
    "odata_base_url": "https://s4h.example.com/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV",
    "sap_client": "100",
}


def build_sap(table, credentials=None, http=None, mode=None):
    db = DynamoDBService(table_name=TEST_TABLE_NAME, client=table)
    secret_service = FakeSecretManager({SAP_SECRET_NAME: credentials or {}})
    return SapIntegrationService(
        db_service=db, secret_service=secret_service,
        http_client=http or FakeHTTPClient(), mode=mode,
    )


class TestSapPersistentSandbox(unittest.TestCase):
    """Default mode when no SAP credentials are provisioned."""

    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def test_mode_is_sandbox_without_credentials(self):
        sap = build_sap(self.table)
        self.assertEqual(sap.mode, MODE_SANDBOX)
        self.assertFalse(sap.is_live)
        self.assertEqual(sap._odata_path(), "/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV")

    def test_mode_is_live_with_credentials(self):
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS)
        self.assertEqual(sap.mode, MODE_LIVE)
        self.assertTrue(sap.is_live)

    def test_pr_payload_shape(self):
        sap = build_sap(self.table)
        payload = sap.build_pr_payload(
            sku_id="SKU-ALM-003", sku_name="Telur Ayam Ras Segar 1kg",
            quantity=20, storage_location="STR-ALMADINA-001", base_unit="KG",
        )
        d = payload.to_dict()
        self.assertEqual(d["PurchaseRequisitionType"], "NB")
        self.assertEqual(len(d["PurchaseRequisitionItems"]), 1)
        item = d["PurchaseRequisitionItems"][0]
        self.assertEqual(item["Material"], "SKU-ALM-003")
        self.assertEqual(item["RequestedQuantity"], 20)
        self.assertEqual(item["BaseUnit"], "KG")
        self.assertEqual(item["ShortText"], "AutoReplenish.ai - Telur Ayam Ras Segar 1kg")
        self.assertRegex(item["DeliveryDate"], r"^\d{4}-\d{2}-\d{2}$")

    def test_sandbox_returns_sap_exact_odata_envelope(self):
        sap = build_sap(self.table)
        resp = sap.create_purchase_requisition("REQ-SBX-0001", make_pr_payload())

        self.assertTrue(resp.success)
        self.assertEqual(resp.mode, MODE_SANDBOX)
        self.assertEqual(resp.status_code, 201)
        self.assertIsNotNone(resp.sap_pr_id)

        odata = resp.odata_response
        self.assertIn("d", odata)
        self.assertEqual(odata["d"]["PurchaseRequisition"], resp.sap_pr_id)
        self.assertEqual(odata["d"]["PurchaseRequisitionType"], "NB")
        self.assertIn("ToPurchaseReqnItem", odata["d"])
        self.assertEqual(len(odata["d"]["ToPurchaseReqnItem"]), 1)
        self.assertEqual(odata["d"]["ToPurchaseReqnItem"][0]["Material"], "SKU-ALM-003")

    def test_pr_id_is_a_10_digit_sap_style_number(self):
        sap = build_sap(self.table)
        resp = sap.create_purchase_requisition("REQ-SBX-0002", make_pr_payload())
        self.assertRegex(resp.sap_pr_id, r"^\d{10}$")

    def test_pr_ids_are_monotonic_and_unique(self):
        sap = build_sap(self.table)
        ids = [
            sap.create_purchase_requisition(f"REQ-SBX-SEQ-{i}", make_pr_payload()).sap_pr_id
            for i in range(4)
        ]
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(sorted(ids), ids)

    def test_ledger_is_persisted_to_dynamodb(self):
        sap = build_sap(self.table)
        resp = sap.create_purchase_requisition("REQ-SBX-LEDGER", make_pr_payload(quantity=30))

        txn = sap.db.get_sap_transaction("REQ-SBX-LEDGER")
        self.assertIsNotNone(txn)
        self.assertEqual(txn.status, "SUCCESS")
        self.assertEqual(txn.mode, MODE_SANDBOX)
        self.assertEqual(txn.quantity, 30)
        self.assertEqual(txn.sap_pr_id, resp.sap_pr_id)

    def test_idempotency_survives_cold_start(self):
        """A NEW service instance (fresh Lambda container) must not duplicate a PR."""
        first = build_sap(self.table)
        total_before = len(first.db.list_sap_transactions())
        resp1 = first.create_purchase_requisition("REQ-SBX-IDEMPOTENT", make_pr_payload())
        del first  # simulate container recycle

        second = build_sap(self.table)
        resp2 = second.create_purchase_requisition("REQ-SBX-IDEMPOTENT", make_pr_payload())

        self.assertTrue(resp2.success)
        self.assertEqual(resp1.sap_pr_id, resp2.sap_pr_id)
        rows = [
            t for t in second.db.list_sap_transactions()
            if t.request_id == "REQ-SBX-IDEMPOTENT"
        ]
        self.assertEqual(len(rows), 1)
        # Exactly one row was created overall, i.e. the retry wrote nothing.
        self.assertEqual(len(second.db.list_sap_transactions()), total_before + 1)

    def test_existing_failure_is_not_replayed_as_success(self):
        sap = build_sap(self.table)
        # Force a failed ledger entry.
        from src.models.schema import SapTransactionRecord
        sap.db.put_sap_transaction(SapTransactionRecord(
            request_id="REQ-SBX-FAILED", store_id="STR-ALMADINA-001", sku_id="SKU-ALM-003",
            quantity=10, status="FAILED", sap_pr_id=None, mode=MODE_SANDBOX,
            created_at="2026-01-01T00:00:00+00:00", error_message="gateway timeout",
        ))
        resp = sap.create_purchase_requisition("REQ-SBX-FAILED", make_pr_payload())
        self.assertTrue(resp.success)  # retry allowed, and now recorded SUCCESS
        self.assertEqual(sap.db.get_sap_transaction("REQ-SBX-FAILED").status, "SUCCESS")

    def test_connection_status_reports_sandbox_metrics(self):
        sap = build_sap(self.table)
        sap.create_purchase_requisition("REQ-SBX-METRIC", make_pr_payload())
        status = sap.get_connection_status()

        self.assertEqual(status["mode"], MODE_SANDBOX)
        self.assertEqual(status["connection_status"], "SANDBOX")
        self.assertEqual(status["metrics"]["total_pr_generated"], 1)
        self.assertEqual(status["metrics"]["total_pr_failed"], 0)
        self.assertEqual(len(status["recent_transactions"]), 1)
        self.assertIn("API_PURCHASEREQ_PROCESS_SRV", status["odata_endpoint"])


class TestSapLiveMode(unittest.TestCase):
    """LIVE mode: OAuth2 token + CSRF handshake + deep-insert POST."""

    @classmethod
    def setUpClass(cls):
        cls._ctx = moto_dynamo_table()
        cls.table = cls._ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def _token_response(self, token="live-token-abc", expires_in=3600):
        return FakeHTTPResponse(200, {"access_token": token, "token_type": "Bearer", "expires_in": expires_in})

    def _csrf_response(self, token="csrf-xyz"):
        resp = FakeHTTPResponse(200, {"d": {"EntitySets": [] }})
        resp.headers = {"x-csrf-token": token, "set-cookie": "SAP_SESSIONID=S1_500"}
        return resp

    def _pr_created_response(self, pr_id="0014500019999"):
        return FakeHTTPResponse(201, {"d": {"PurchaseRequisition": pr_id}})

    def test_oauth_token_flow(self):
        http = FakeHTTPClient([self._token_response()])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)

        token = sap.get_access_token()
        self.assertEqual(token, "live-token-abc")

        call = http.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "https://s4h.example.com/sap/bc/sec/oauth2/token")
        self.assertEqual(call["data"]["grant_type"], "client_credentials")
        self.assertTrue(call["headers"]["Authorization"].startswith("Basic "))

    def test_token_is_cached_and_reused(self):
        http = FakeHTTPClient([self._token_response()])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)
        sap.get_access_token()
        sap.get_access_token()
        self.assertEqual(len(http.calls), 1)

    def test_token_expiry_triggers_refetch(self):
        http = FakeHTTPClient([
            self._token_response("token-1", expires_in=1),
            self._token_response("token-2"),
        ])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)
        sap.get_access_token()
        time.sleep(1.1)
        sap.get_access_token()
        self.assertEqual(len(http.calls), 2)

    def test_csrf_token_fetch_uses_fetch_header_and_sap_client(self):
        http = FakeHTTPClient([self._token_response(), self._csrf_response()])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)

        csrf = sap._get_csrf_token()
        self.assertEqual(csrf["token"], "csrf-xyz")

        call = http.calls[1]
        self.assertEqual(call["url"], "https://s4h.example.com/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV")
        self.assertEqual(call["headers"]["X-CSRF-Token"], "Fetch")
        self.assertEqual(call["headers"]["x-sap-client"], "100")
        self.assertTrue(call["headers"]["Authorization"].startswith("Bearer "))

    def test_full_create_pr_sequence_in_live_mode(self):
        http = FakeHTTPClient([
            self._token_response(),
            self._csrf_response(),
            self._pr_created_response("0014500019999"),
        ])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)

        resp = sap.create_purchase_requisition("REQ-LIVE-0001", make_pr_payload(quantity=20))

        self.assertTrue(resp.success)
        self.assertEqual(resp.mode, MODE_LIVE)
        self.assertEqual(resp.sap_pr_id, "0014500019999")
        self.assertEqual(len(http.calls), 3)

        post_call = http.calls[2]
        self.assertEqual(post_call["method"], "POST")
        self.assertEqual(
            post_call["url"],
            "https://s4h.example.com/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV/A_PurchaseRequisitionHeader",
        )
        self.assertEqual(post_call["json"]["PurchaseRequisitionType"], "NB")
        self.assertEqual(post_call["headers"]["X-CSRF-Token"], "csrf-xyz")
        self.assertIn("Cookie", post_call["headers"])

    def test_live_failure_is_persisted_as_failed_ledger_entry(self):
        http = FakeHTTPClient([
            self._token_response(),
            self._csrf_response(),
        ] + [FakeHTTPResponse(500, {}, text="gateway timeout") for _ in range(3)])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)

        resp = sap.create_purchase_requisition("REQ-LIVE-FAIL", make_pr_payload())
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_message.__class__, str)
        self.assertIn("HTTP 500", resp.error_message)

        txn = sap.db.get_sap_transaction("REQ-LIVE-FAIL")
        self.assertIsNotNone(txn)
        self.assertEqual(txn.status, "FAILED")

    def test_4xx_rejection_is_not_retried(self):
        http = FakeHTTPClient([
            self._token_response(), self._csrf_response(),
            FakeHTTPResponse(400, {"error": "invalid material"}, text="bad request"),
        ])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)

        resp = sap.create_purchase_requisition("REQ-LIVE-400", make_pr_payload())
        self.assertFalse(resp.success)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(http.calls), 3)  # no retry on 4xx

    def test_idempotent_repeat_skips_live_post(self):
        http = FakeHTTPClient([
            self._token_response(), self._csrf_response(),
            self._pr_created_response("0014500020001"),
            # Should never be consumed again
            self._token_response(), self._csrf_response(),
            self._pr_created_response("0014500020002"),
        ])
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS, http=http)

        first = sap.create_purchase_requisition("REQ-LIVE-IDEM", make_pr_payload())
        second = sap.create_purchase_requisition("REQ-LIVE-IDEM", make_pr_payload())

        self.assertEqual(first.sap_pr_id, "0014500020001")
        self.assertEqual(second.sap_pr_id, "0014500020001")
        self.assertEqual(len(http.calls), 3)

    def test_live_connection_status_reports_host(self):
        sap = build_sap(self.table, credentials=LIVE_CREDENTIALS)
        status = sap.get_connection_status()
        self.assertEqual(status["connection_status"], "ONLINE")
        self.assertEqual(status["sap_host"], "https://s4h.example.com")
        self.assertEqual(status["mode"], MODE_LIVE)


if __name__ == "__main__":
    unittest.main()
