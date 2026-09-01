"""Telegram Webhook Lambda Handler.

Handles Store Manager actions:
- Approve -> Triggers SAP PR creation (Idempotent).
- Edit Quantity -> Validates MOQ/packaging multiples, creates PR with final qty, logs feedback.
- Reject -> Records rejection feedback, cancels PR creation.
- Prevents double clicks and handles expired timeouts.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from ..config import logger
from ..models.schema import TelegramStateRecord, FeedbackLogRecord
from ..services.dynamodb_service import DynamoDBService
from ..services.sap_service import SapIntegrationService
from ..services.moq_packaging_service import MoqPackagingService

class TelegramWebhookProcessor:
    """Processes incoming Telegram updates."""

    def __init__(self, db_service: DynamoDBService, sap_service: SapIntegrationService):
        self.db = db_service
        self.sap = sap_service

    def handle_callback_query(self, callback_data: str, user_id: str = "user_budi") -> Dict[str, Any]:
        """
        Handle callback format: ACTION:request_id
        Examples:
            APPROVE:REQ-20260616-0001
            EDIT:REQ-20260616-0001
            REJECT:REQ-20260616-0001
        """
        parts = callback_data.split(":", 1)
        if len(parts) != 2:
            return {"status": "error", "message": "Invalid callback data format"}

        action, request_id = parts[0].upper(), parts[1]
        state = self.db.get_telegram_state(request_id)

        if not state:
            return {"status": "error", "message": f"Request {request_id} not found."}

        # 1. Check Timeout (PRD Section 11.8 & 15.5)
        now_iso = datetime.now(timezone.utc).isoformat()
        if state.expires_at and now_iso > state.expires_at:
            if state.status == "PENDING_APPROVAL":
                self.db.update_telegram_state_status(request_id, "TIMEOUT")
            return {
                "status": "timeout",
                "message": "⏱️ Sesi persetujuan telah kedaluwarsa (Timeout > 4 Jam). Silakan hubungi tim Supply Chain.",
                "state": state.to_dict()
            }

        # 2. Prevent Duplicate Actions (PRD Section 15.6)
        if state.status in ("APPROVED", "PR_CREATED"):
            return {
                "status": "already_processed",
                "message": f"ℹ️ Permintaan ini sudah disetujui sebelumnya (PR: {state.sap_pr_id or 'Diproses'}).",
                "state": state.to_dict()
            }

        if state.status == "REJECTED":
            return {
                "status": "already_processed",
                "message": "ℹ️ Permintaan ini sudah ditolak sebelumnya.",
                "state": state.to_dict()
            }

        # 3. Action Dispatcher
        if action == "APPROVE":
            return self._handle_approve(state)
        elif action == "EDIT":
            return {
                "status": "edit_prompt",
                "message": f"✏️ Silakan masukkan jumlah order baru untuk {state.sku_id} (Rekomendasi AI: {state.recommended_qty} pcs):",
                "state": state.to_dict()
            }
        elif action == "REJECT":
            return {
                "status": "reject_prompt",
                "message": f"❌ Mohon berikan alasan penolakan untuk {state.sku_id}:",
                "state": state.to_dict()
            }
        else:
            return {"status": "error", "message": f"Aksi '{action}' tidak dikenal."}

    def _handle_approve(self, state: TelegramStateRecord) -> Dict[str, Any]:
        """Execute approval and create SAP Purchase Requisition."""
        qty_to_order = state.final_qty or state.recommended_qty
        now_str = datetime.now(timezone.utc).isoformat()

        # Update status to APPROVED
        self.db.update_telegram_state_status(state.request_id, "APPROVED")

        # Build and send PR to SAP S/4HANA
        payload = self.sap.build_pr_payload(
            sku_id=state.sku_id,
            sku_name=f"Material {state.sku_id}",
            quantity=qty_to_order,
            storage_location=state.store_id
        )
        sap_resp = self.sap.create_purchase_requisition(state.request_id, payload)

        if sap_resp.success:
            self.db.update_telegram_state_status(
                state.request_id,
                "PR_CREATED",
                sap_pr_id=sap_resp.sap_pr_id
            )
            # Update Audit Log
            audit_log = self.db.get_audit_log_by_request_id(state.request_id)
            if audit_log:
                audit_log.human_action = "APPROVED"
                audit_log.human_final_qty = qty_to_order
                audit_log.sap_pr_status = "SUCCESS"
                audit_log.sap_pr_id = sap_resp.sap_pr_id
                audit_log.approved_at = now_str
                audit_log.completed_at = now_str
                self.db.put_audit_log(audit_log)

            msg = (
                f"✅ *Purchase Requisition Berhasil Dibuat di SAP S/4HANA*\n\n"
                f"📋 *PR ID:* `{sap_resp.sap_pr_id}`\n"
                f"🏷️ *SKU:* `{state.sku_id}`\n"
                f"📦 *Kuantitas:* {qty_to_order} Pcs\n"
                f"⏰ *Waktu:* {now_str[:19]}"
            )
            return {"status": "success", "message": msg, "sap_pr_id": sap_resp.sap_pr_id}
        else:
            self.db.update_telegram_state_status(
                state.request_id,
                "FAILED_SAP",
                sap_error_message=sap_resp.error_message
            )
            audit_log = self.db.get_audit_log_by_request_id(state.request_id)
            if audit_log:
                audit_log.human_action = "APPROVED"
                audit_log.sap_pr_status = "FAILED_SAP"
                self.db.put_audit_log(audit_log)

            msg = (
                f"⚠️ *Gagal Membuat PR di SAP S/4HANA*\n\n"
                f"Error: {sap_resp.error_message}\n"
                f"Event telah dialihkan ke antrian retry/DLQ untuk investigasi IT."
            )
            return {"status": "failed_sap", "message": msg, "error": sap_resp.error_message}

    def handle_manual_qty_edit(self, request_id: str, new_qty: int) -> Dict[str, Any]:
        """Process manual quantity edit from store manager."""
        state = self.db.get_telegram_state(request_id)
        if not state:
            return {"status": "error", "message": "Request tidak ditemukan."}

        if new_qty <= 0:
            return {"status": "error", "message": "Jumlah order harus lebih besar dari 0."}

        sku_profile = self.db.get_sku(state.sku_id)
        moq = sku_profile.moq if sku_profile else 1
        pack_mult = sku_profile.packaging_multiple if sku_profile else 1

        # Adjust quantity with packaging policy
        adj_qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=new_qty,
            moq=moq,
            packaging_multiple=pack_mult
        )

        now_str = datetime.now(timezone.utc).isoformat()

        # Record Feedback log for Human Override
        feedback = FeedbackLogRecord(
            store_id=state.store_id,
            sku_id=state.sku_id,
            action="EDITED",
            reason=f"Store manager manually changed qty from {state.recommended_qty} to {adj_qty}",
            original_recommended_qty=state.recommended_qty,
            final_qty=adj_qty,
            created_at=now_str
        )
        self.db.put_feedback_log(feedback)

        # Update state and trigger SAP PR
        state.final_qty = adj_qty
        self.db.put_telegram_state(state)

        # Create PR with edited qty
        return self._handle_approve(state)

    def handle_rejection(self, request_id: str, reason: str) -> Dict[str, Any]:
        """Process rejection with feedback logging."""
        state = self.db.get_telegram_state(request_id)
        if not state:
            return {"status": "error", "message": "Request tidak ditemukan."}

        now_str = datetime.now(timezone.utc).isoformat()
        self.db.update_telegram_state_status(request_id, "REJECTED", rejection_reason=reason)

        # Store Feedback in DynamoDB
        feedback = FeedbackLogRecord(
            store_id=state.store_id,
            sku_id=state.sku_id,
            action="REJECTED",
            reason=reason,
            original_recommended_qty=state.recommended_qty,
            created_at=now_str
        )
        self.db.put_feedback_log(feedback)

        # Update Audit Log
        audit_log = self.db.get_audit_log_by_request_id(request_id)
        if audit_log:
            audit_log.human_action = "REJECTED"
            audit_log.rejection_reason = reason
            audit_log.completed_at = now_str
            self.db.put_audit_log(audit_log)

        msg = (
            f"❌ *Rekomendasi Ditolak*\n\n"
            f"Alasan penolakan telah disimpan sebagai feedback pembelajaran agen AI:\n"
            f"_{reason}_\n\n"
            f"Tidak ada dokumen PR yang dibuat di SAP S/4HANA."
        )
        return {"status": "rejected", "message": msg}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for Telegram Webhook."""
    db_service = DynamoDBService()
    sap_service = SapIntegrationService()
    processor = TelegramWebhookProcessor(db_service, sap_service)

    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            body = {}

    # Check for callback query
    callback_query = body.get("callback_query")
    if callback_query:
        callback_data = callback_query.get("data", "")
        result = processor.handle_callback_query(callback_data)
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result)
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ignored", "message": "No actionable Telegram payload"})
    }
