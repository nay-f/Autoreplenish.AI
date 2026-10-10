"""Telegram Webhook Lambda Handler.

Handles Store Manager actions (PRD Section 11.7, 11.8, 14.4, 15.6):
- Approve  -> dispatch SAP PR creation (async via SQS, with inline fallback).
- Edit Qty -> validate MOQ / packaging multiples, then create the PR.
- Reject   -> record feedback, cancel PR creation.
- ``answerCallbackQuery`` is always sent first so the Telegram client stops its
  spinner, then the original card is updated with ``editMessageText``.
- Prevents double clicks, expired approvals, and duplicate PRs.

Update shapes handled: ``callback_query`` (button press) and ``message``
(free-text replies for the EDIT / REJECT follow-up questions).
"""

import json
from typing import Any, Dict, Optional

from datetime import datetime, timezone

from ..config import logger, SAP_PR_QUEUE_URL, TELEGRAM_SECRET_NAME
from ..models.schema import (
    AWAITING_QTY,
    AWAITING_REJECT_REASON,
    TelegramStateRecord,
    FeedbackLogRecord,
)
from ..services.dynamodb_service import DynamoDBService
from ..services.sap_service import SapIntegrationService
from ..services.moq_packaging_service import MoqPackagingService
from ..services.telegram_service import TelegramService
from ..services.secrets_service import SecretManagerService


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelegramWebhookProcessor:
    """Processes incoming Telegram updates."""

    def __init__(
        self,
        db_service: DynamoDBService,
        sap_service: Optional[SapIntegrationService] = None,
        telegram_service: Optional[TelegramService] = None,
    ):
        self.db = db_service
        self.sap = sap_service or SapIntegrationService(db_service=db_service)
        self.telegram = telegram_service or TelegramService(
            secret_service=getattr(self.sap, "_secret_service", None)
        )

    # =========================================================
    # Entry point
    # =========================================================
    def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """Route a single Telegram Update object."""
        if update.get("callback_query"):
            return self._handle_callback_update(update["callback_query"])
        if update.get("message"):
            return self._handle_message_update(update["message"])
        return {"status": "ignored", "message": "No actionable Telegram payload"}

    def handle_callback_query(self, callback_data: str, callback_query_id: Optional[str] = None) -> Dict[str, Any]:
        """Handle a raw ``ACTION:request_id`` callback payload.

        Convenience entry point used by tests and non-webhook transports.
        """
        return self._handle_callback_update({"id": callback_query_id, "data": callback_data})

    # =========================================================
    # Callback query (inline button)
    # =========================================================
    def _handle_callback_update(self, callback_query: Dict[str, Any]) -> Dict[str, Any]:
        data = callback_query.get("data", "")
        callback_query_id = callback_query.get("id")
        from_user = callback_query.get("from") or {}
        user_id = str(from_user.get("id", "unknown_user"))

        # 1. Acknowledge the click IMMEDIATELY (PRD 14.4) so the Telegram client
        #    stops its spinner before any DynamoDB / Bedrock / SAP work begins.
        #    Only the first answerCallbackQuery is surfaced to the user, so the
        #    detailed outcome is delivered through editMessageText instead.
        self.telegram.answer_callback_query(callback_query_id, "⏳ Memproses permintaan...")

        parts = data.split(":", 1)
        if len(parts) != 2:
            return {"status": "error", "message": "Invalid callback data format"}

        action, request_id = parts[0].upper(), parts[1]
        state = self.db.get_telegram_state(request_id)

        if not state:
            return {"status": "error", "message": f"Request {request_id} not found."}

        # 2. Timeout enforcement (PRD 11.8) - passive check on every interaction.
        if self._is_expired(state):
            self.db.update_telegram_state_status(request_id, "TIMEOUT")
            self._refresh_card(state, status_line="⏱️ Sesi persetujuan kedaluwarsa (Timeout > 4 Jam).")
            return {
                "status": "timeout",
                "message": "⏱️ Sesi persetujuan telah kedaluwarsa. Hubungi tim Supply Chain.",
            }

        # 3. Duplicate action guard (PRD 15.6)
        duplicate = self._duplicate_guard_message(state)
        if duplicate:
            self.telegram.send_message(state.telegram_chat_id, duplicate)
            return {"status": "already_processed", "message": duplicate}

        # 4. Action dispatcher
        if action == "APPROVE":
            result = self.handle_approve(state)
        elif action == "EDIT":
            result = self.handle_edit_request(state)
        elif action == "REJECT":
            result = self.handle_reject_request(state)
        else:
            self.telegram.send_message(state.telegram_chat_id, f"⚠️ Aksi '{action}' tidak dikenal.")
            return {"status": "error", "message": f"Aksi '{action}' tidak dikenal."}

        result["actor_user_id"] = user_id
        return result

    # =========================================================
    # Free-text message (EDIT qty / REJECT reason)
    # =========================================================
    def _handle_message_update(self, message: Dict[str, Any]) -> Dict[str, Any]:
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = (message.get("text") or "").strip()

        if not chat_id:
            return {"status": "ignored", "message": "Empty message"}

        if text.startswith("/register_store") or text.startswith("/tambah_toko"):
            self.telegram.send_message(
                chat_id,
                "🏪 <b>Pendaftaran Toko Baru (AutoReplenish.ai)</b>\n"
                "Untuk mendaftarkan toko baru beserta deteksi koordinat GPS dan pemilihan mode kasir/SAP, "
                "silakan kirimkan nama toko Anda atau jalankan <code>python run_local_prod.py</code>."
            )
            return {"status": "success", "message": "Store onboarding prompt sent"}

        if text.startswith("/analisa") or text.startswith("/cek_stok"):
            self.telegram.send_message(
                chat_id,
                "⚡ <b>Analisa Stok On-Demand Dipicu</b>\n"
                "Pipeline evaluasi penalaran Bedrock sedang memproses stok fisik dan kondisi cuaca satelit toko Anda."
            )
            return {"status": "success", "message": "On-demand analysis prompt sent"}

        if not text:
            return {"status": "ignored", "message": "Empty message text"}

        request_id = self.db.get_chat_pending_request(chat_id)
        if not request_id:
            self.telegram.send_message(
                chat_id,
                "Ketik /start atau tekan tombol pada kartu rekomendasi terbaru untuk mulai."
            )
            return {"status": "ignored", "message": "No pending request for chat"}

        state = self.db.get_telegram_state(request_id)
        if not state:
            self.db.clear_chat_pending_request(chat_id)
            return {"status": "error", "message": f"Request {request_id} not found."}

        if self._is_expired(state):
            self.db.update_telegram_state_status(request_id, "TIMEOUT")
            self.db.clear_chat_pending_request(chat_id)
            self._refresh_card(state, status_line="⏱️ Sesi persetujuan kedaluwarsa.")
            return {"status": "timeout", "message": "Approval window expired"}

        if state.awaiting_input == AWAITING_QTY:
            return self.handle_manual_qty_edit(request_id, text)
        if state.awaiting_input == AWAITING_REJECT_REASON:
            return self.handle_rejection(request_id, text)

        self.db.clear_chat_pending_request(chat_id)
        return {"status": "ignored", "message": "Chat is not awaiting an input"}

    # =========================================================
    # Guards
    # =========================================================
    @staticmethod
    def _is_expired(state: TelegramStateRecord) -> bool:
        return bool(state.expires_at) and _utc_now_iso() > state.expires_at

    @staticmethod
    def _duplicate_guard_message(state: TelegramStateRecord) -> Optional[str]:
        if state.status in ("APPROVED", "PR_CREATED", "EDITED", "QUEUED_SAP"):
            return (
                f"ℹ️ Permintaan ini sudah disetujui sebelumnya "
                f"(PR: {state.sap_pr_id or 'sedang diproses'})."
            )
        if state.status == "REJECTED":
            return "ℹ️ Permintaan ini sudah ditolak sebelumnya."
        if state.status == "TIMEOUT":
            return "ℹ️ Permintaan ini sudah kedaluwarsa."
        return None

    # =========================================================
    # Actions
    # =========================================================
    def handle_approve(self, state: TelegramStateRecord) -> Dict[str, Any]:
        """Approve the AI recommendation and dispatch PR creation to SAP."""
        qty_to_order = state.final_qty or state.recommended_qty

        # Optimistic state transition BEFORE dispatch so a second click is caught.
        self.db.update_telegram_state_status(state.request_id, "APPROVED", awaiting_input=None)
        self.db.clear_chat_pending_request(state.telegram_chat_id)

        payload = self.sap.build_pr_payload(
            sku_id=state.sku_id,
            sku_name=f"Material {state.sku_id}",
            quantity=qty_to_order,
            storage_location=state.store_id,
        )

        if SAP_PR_QUEUE_URL and self._dispatch_to_sqs(state.request_id, state.store_id, qty_to_order):
            self.db.update_telegram_state_status(state.request_id, "QUEUED_SAP")
            self._refresh_card(
                state,
                status_line=(
                    f"✅ *Disetujui* — {qty_to_order} Pc\n"
                    f"⏳ Purchase Requisition sedang diterbitkan oleh SAP Worker."
                ),
            )
            return {
                "status": "queued_sap",
                "message": f"PR untuk {state.sku_id} ({qty_to_order} Pc) masuk antrian SAP.",
            }

        return self._create_pr_inline(state, qty_to_order, payload)

    def _create_pr_inline(
        self,
        state: TelegramStateRecord,
        qty_to_order: int,
        payload: Any
    ) -> Dict[str, Any]:
        sap_resp = self.sap.create_purchase_requisition(
            request_id=state.request_id,
            payload=payload,
            store_id=state.store_id,
        )

        if sap_resp.success:
            self.db.update_telegram_state_status(
                state.request_id, "PR_CREATED", sap_pr_id=sap_resp.sap_pr_id
            )
            self._finalize_audit(state, "APPROVED", qty_to_order, sap_resp)
            self._refresh_card(
                state,
                status_line=(
                    f"✅ *Purchase Requisition Dibuat di SAP S/4HANA*\n\n"
                    f"📋 *PR ID:* `{sap_resp.sap_pr_id}`\n"
                    f"🏷️ *SKU:* `{state.sku_id}`\n"
                    f"📦 *Kuantitas:* {qty_to_order} Pc\n"
                    f"🅼️ *Mode:* {sap_resp.mode}"
                ),
            )
            return {
                "status": "success",
                "message": "Purchase Requisition berhasil dibuat.",
                "sap_pr_id": sap_resp.sap_pr_id,
                "mode": sap_resp.mode,
            }

        self.db.update_telegram_state_status(
            state.request_id, "FAILED_SAP", sap_error_message=sap_resp.error_message
        )
        self._finalize_audit(state, "APPROVED", qty_to_order, sap_resp)
        self._refresh_card(
            state,
            status_line=(
                f"⚠️ *Gagal Membuat PR di SAP S/4HANA*\n\n"
                f"Error: {sap_resp.error_message}\n"
                f"Event dialihkan ke antrian retry/DLQ untuk investigasi IT."
            ),
        )
        return {
            "status": "failed_sap",
            "message": sap_resp.error_message,
        }

    def handle_edit_request(self, state: TelegramStateRecord) -> Dict[str, Any]:
        """Prompt the manager for a new quantity and hold the conversation state."""
        self.db.update_telegram_state_status(state.request_id, "PENDING_APPROVAL", awaiting_input=AWAITING_QTY)
        self.db.set_chat_pending_request(state.telegram_chat_id, state.request_id)
        self.telegram.send_message(
            chat_id=state.telegram_chat_id,
            text=(
                f"✏️ Masukkan jumlah order baru untuk `{state.sku_id}` "
                f"(Rekomendasi AI: {state.recommended_qty} Pc).\n"
                f"Kirim angka saja, misal: 24"
            ),
        )
        return {
            "status": "edit_prompt",
            "message": f"Menunggu input jumlah baru untuk {state.sku_id}.",
        }

    def handle_reject_request(self, state: TelegramStateRecord) -> Dict[str, Any]:
        """Prompt the manager for a rejection reason and hold the conversation state."""
        self.db.update_telegram_state_status(
            state.request_id, "PENDING_APPROVAL", awaiting_input=AWAITING_REJECT_REASON
        )
        self.db.set_chat_pending_request(state.telegram_chat_id, state.request_id)
        self.telegram.send_message(
            chat_id=state.telegram_chat_id,
            text=f"❌ Mohon berikan alasan penolakan untuk `{state.sku_id}`:",
        )
        return {
            "status": "reject_prompt",
            "message": f"Menunggu alasan penolakan untuk {state.sku_id}.",
        }

    def handle_manual_qty_edit(self, request_id: str, raw_qty: str) -> Dict[str, Any]:
        """Process a manual quantity edit with MOQ / packaging validation."""
        state = self.db.get_telegram_state(request_id)
        if not state:
            return {"status": "error", "message": "Request tidak ditemukan."}

        try:
            new_qty = int(float(raw_qty))
        except (TypeError, ValueError):
            self.telegram.answer_callback_query(None, "Jumlah harus berupa angka.", show_alert=True)
            self.telegram.send_message(state.telegram_chat_id, "⚠️ Jumlah order harus berupa angka, misal: 24")
            return {"status": "error", "message": "Jumlah order harus berupa angka."}

        if new_qty <= 0:
            self.telegram.send_message(state.telegram_chat_id, "⚠️ Jumlah order harus lebih besar dari 0.")
            return {"status": "error", "message": "Jumlah order harus lebih besar dari 0."}

        sku_profile = self.db.get_sku(state.sku_id)
        moq = sku_profile.moq if sku_profile else 1
        pack_mult = sku_profile.packaging_multiple if sku_profile else 1

        adj_qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=new_qty,
            moq=moq,
            packaging_multiple=pack_mult,
            category=sku_profile.category if sku_profile else "Non-Perishable",
            shelf_life_days=sku_profile.shelf_life_days if sku_profile else 365,
            is_fragile=sku_profile.is_fragile if sku_profile else False,
        )
        self.db.clear_chat_pending_request(state.telegram_chat_id)

        self.db.put_feedback_log(FeedbackLogRecord(
            store_id=state.store_id,
            sku_id=state.sku_id,
            action="EDITED",
            reason=f"Store manager mengubah jumlah dari {state.recommended_qty} ke {adj_qty} ({note})",
            original_recommended_qty=state.recommended_qty,
            final_qty=adj_qty,
            created_at=_utc_now_iso(),
        ))

        self.db.update_telegram_state_status(
            state.request_id, "APPROVED", final_qty=adj_qty, awaiting_input=None
        )
        payload = self.sap.build_pr_payload(
            sku_id=state.sku_id,
            sku_name=f"Material {state.sku_id}",
            quantity=adj_qty,
            storage_location=state.store_id,
        )
        result = self._create_pr_inline(state, adj_qty, payload)

        if state.telegram_message_id:
            self.telegram.send_message(
                state.telegram_chat_id,
                f"✏️ Jumlah diubah menjadi *{adj_qty} Pc* ({note}).",
            )
        return result

    def handle_rejection(self, request_id: str, reason: str) -> Dict[str, Any]:
        """Process a rejection, log the feedback, and cancel PR creation."""
        state = self.db.get_telegram_state(request_id)
        if not state:
            return {"status": "error", "message": "Request tidak ditemukan."}

        reason = (reason or "").strip() or "Tidak ada alasan diberikan"
        self.db.update_telegram_state_status(
            request_id, "REJECTED", rejection_reason=reason, awaiting_input=None
        )
        self.db.clear_chat_pending_request(state.telegram_chat_id)

        self.db.put_feedback_log(FeedbackLogRecord(
            store_id=state.store_id,
            sku_id=state.sku_id,
            action="REJECTED",
            reason=reason,
            original_recommended_qty=state.recommended_qty,
            created_at=_utc_now_iso(),
        ))

        audit_log = self.db.get_audit_log_by_request_id(request_id)
        if audit_log:
            audit_log.human_action = "REJECTED"
            audit_log.rejection_reason = reason
            audit_log.completed_at = _utc_now_iso()
            self.db.put_audit_log(audit_log)

        self._refresh_card(
            state,
            status_line=(
                f"❌ *Rekomendasi Ditolak*\n\n"
                f"Alasan: _{reason}_\n\n"
                f"Tidak ada dokumen PR yang dibuat di SAP S/4HANA."
            ),
        )
        return {"status": "rejected", "message": reason}

    # =========================================================
    # Helpers
    # =========================================================
    def _dispatch_to_sqs(self, request_id: str, store_id: str, quantity: int) -> bool:
        """Enqueue the SAP PR job so the worker Lambda performs the mutation.

        FIFO deduplication is used when the queue is FIFO (infra/sqs.tf), and the
        call degrades gracefully to a standard-queue send otherwise.
        """
        if not SAP_PR_QUEUE_URL:
            return False

        body = json.dumps({
            "request_id": request_id,
            "store_id": store_id,
            "quantity": quantity,
        })

        try:
            import boto3
            sqs = boto3.client("sqs")
            is_fifo = SAP_PR_QUEUE_URL.endswith(".fifo")
            kwargs = {"QueueUrl": SAP_PR_QUEUE_URL, "MessageBody": body}
            if is_fifo:
                kwargs["MessageGroupId"] = request_id
                kwargs["MessageDeduplicationId"] = request_id
            sqs.send_message(**kwargs)
            logger.info(f"SAP PR job enqueued to SQS for request {request_id} (fifo={is_fifo})")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue SAP PR job for {request_id}: {e}")
            return False

    def _refresh_card(self, state: TelegramStateRecord, status_line: str) -> None:
        """Rewrite the original card with the resolved outcome."""
        self.telegram.edit_message_text(
            chat_id=state.telegram_chat_id,
            message_id=state.telegram_message_id,
            text=(
                f"📦 *AUTOREPLENISH.AI — Status Replenishment*\n"
                f"🏪 *Toko:* {state.store_id}\n"
                f"🏷️ *SKU:* {state.sku_id}\n\n"
                f"{status_line}\n\n"
                f"Ref: `{state.request_id}`"
            ),
            reply_markup={"inline_keyboard": []},
        )

    def _finalize_audit(
        self,
        state: TelegramStateRecord,
        action: str,
        final_qty: int,
        sap_resp: Any
    ) -> None:
        audit_log = self.db.get_audit_log_by_request_id(state.request_id)
        if not audit_log:
            return
        now = _utc_now_iso()
        audit_log.human_action = action
        audit_log.human_final_qty = final_qty
        audit_log.sap_pr_status = "SUCCESS" if sap_resp.success else "FAILED_SAP"
        audit_log.sap_pr_id = sap_resp.sap_pr_id
        audit_log.sap_mode = sap_resp.mode
        audit_log.approved_at = now
        audit_log.completed_at = now
        self.db.put_audit_log(audit_log)


def _webhook_secret() -> str:
    """Resolve the configured Telegram webhook secret token, if any."""
    try:
        return SecretManagerService().get_telegram_webhook_secret(TELEGRAM_SECRET_NAME)
    except Exception:
        return ""


def _verify_webhook_secret(event: Dict[str, Any], secret: str) -> bool:
    """Validate the X-Telegram-Bot-Api-Secret-Token header (PRD 14.4).

    When no secret is configured (local development) the check is bypassed.
    """
    if not secret:
        return True

    headers = event.get("headers") or {}
    provided = ""
    for key, value in headers.items():
        if key.lower() == "x-telegram-bot-api-secret-token":
            provided = str(value or "")
            break
    return provided == secret


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for the Telegram Webhook (API Gateway v2 payload)."""
    if not _verify_webhook_secret(event, _webhook_secret()):
        logger.warning("Rejected Telegram update with an invalid webhook secret")
        return {"statusCode": 403, "body": json.dumps({"error": "invalid webhook secret"})}

    db_service = DynamoDBService()
    telegram_service = TelegramService()
    sap_service = SapIntegrationService(
        db_service=db_service,
        secret_service=getattr(telegram_service, "_secret_service", None),
    )
    processor = TelegramWebhookProcessor(db_service, sap_service, telegram_service)

    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body) if body else {}
        except Exception:
            body = {}
    if not isinstance(body, dict):
        body = {}

    result = processor.handle_update(body)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result, default=str),
    }
