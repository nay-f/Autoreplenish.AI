"""SQS consumer logic for the SAP transaction boundary."""

import logging
from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.services.sap_service import SAPService

logger = logging.getLogger("autoreplenish.sap_worker")


class SAPWorkerService:
    def __init__(self, db=None, sap=None):
        self.db = db or DynamoDBService()
        self.sap = sap or SAPService(self.db)

    def process(self, message: dict, resolve_store_and_sku) -> dict:
        request_id = message["request_id"]
        message_environment = str(message.get("environment", "")).lower()
        if message_environment != self._environment():
            raise ValueError(
                f"Message environment tidak sesuai worker: {message_environment or 'missing'}"
            )
        state = self.db.get_approval_state(request_id)
        if not state:
            raise ValueError(f"Approval request {request_id} tidak ditemukan.")

        # Fast path for SQS replay after a durable terminal result. This avoids
        # even attempting a second lock/submit and makes duplicate delivery
        # explicitly idempotent.
        if state.status in ("SAP_SUBMITTED", "SAP_SANDBOX_VERIFIED", "SAP_DRY_RUN"):
            return {"request_id": request_id, "status": state.status, "duplicate": True}

        locked = self.db.transition_approval_state(
            request_id,
            expected_current_statuses=["APPROVED", "ENQUEUED", "SAP_FAILED"],
            new_status="SAP_SUBMITTING",
        )
        if not locked:
            latest = self.db.get_approval_state(request_id)
            if latest and latest.status in ("SAP_SUBMITTED", "SAP_SANDBOX_VERIFIED", "SAP_DRY_RUN"):
                return {"request_id": request_id, "status": latest.status, "duplicate": True}
            raise RuntimeError(f"Request {request_id} sedang diproses atau tidak valid.")

        quantity = int(message.get("quantity") or state.final_qty or state.recommended_qty)
        try:
            if quantity < 0 or quantity > 100000:
                raise ValueError("Quantity di luar batas worker (0-100000).")
            store, sku = resolve_store_and_sku(state.store_id, state.sku_id, state.sku_name)
            result = self.sap.create_purchase_requisition(
                store=store,
                sku=sku,
                quantity=quantity,
                idempotency_key=request_id,
            )
            result_status = (
                "SAP_SUBMITTED"
                if result["status"] == "SAP_SUBMITTED"
                else "SAP_SANDBOX_VERIFIED"
                if result["status"] == "BTP_VERIFIED_SANDBOX_PR"
                else "SAP_DRY_RUN"
                if result["status"] == "SAP_DRY_RUN"
                else "SAP_FAILED"
            )
            self.db.transition_approval_state(
                request_id,
                expected_current_statuses=["SAP_SUBMITTING"],
                new_status=result_status,
                final_qty=quantity,
                sap_pr_id=result.get("pr_number"),
            )
            if result_status == "SAP_FAILED":
                raise RuntimeError("SAP menolak atau tidak menerima Purchase Requisition.")
            return result
        except Exception:
            self.db.transition_approval_state(
                request_id,
                expected_current_statuses=["SAP_SUBMITTING"],
                new_status="SAP_FAILED",
                final_qty=quantity,
            )
            raise

    @staticmethod
    def _environment() -> str:
        from backend.src import config

        return config.ENVIRONMENT
