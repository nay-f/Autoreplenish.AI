"""SQS consumer logic for the SAP transaction boundary."""

import logging
from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.services.sap_service import SAPService
from backend.src.services.telegram_service import TelegramService

logger = logging.getLogger("autoreplenish.sap_worker")


class SAPWorkerService:
    def __init__(self, db=None, sap=None, telegram=None):
        self.db = db or DynamoDBService()
        self.sap = sap or SAPService(self.db)
        # Lazy initialization keeps unit tests and messages without Telegram
        # metadata independent from the Telegram/DynamoDB client setup.
        self.telegram = telegram

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
        state_persisted = False
        telegram_notified = False
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
            state_persisted = True
            if result_status == "SAP_FAILED":
                self._notify_telegram(message, state, result_status, result)
                telegram_notified = True
                raise RuntimeError("SAP menolak atau tidak menerima Purchase Requisition.")
            self._notify_telegram(message, state, result_status, result)
            telegram_notified = True
            return result
        except Exception:
            if not state_persisted:
                self.db.transition_approval_state(
                    request_id,
                    expected_current_statuses=["SAP_SUBMITTING"],
                    new_status="SAP_FAILED",
                    final_qty=quantity,
                )
            if not telegram_notified:
                self._notify_telegram(
                    message,
                    state,
                    "SAP_FAILED",
                    {"status": "SAP_FAILED"},
                )
            raise

    def _notify_telegram(self, message: dict, state, result_status: str, result: dict) -> None:
        """Update the approval card without affecting SAP retry semantics."""
        chat_id = str(
            message.get("chat_id") or getattr(state, "telegram_chat_id", "") or ""
        ).strip()
        if not chat_id:
            return

        message_id = message.get("message_id") or getattr(state, "telegram_message_id", None)
        status_copy = {
            "SAP_SUBMITTED": "SUBMITTED (SAP)",
            "SAP_SANDBOX_VERIFIED": "TERUJI DI SANDBOX SAP",
            "SAP_DRY_RUN": "DRY-RUN (SAP TIDAK DITULIS)",
            "SAP_FAILED": "GAGAL - PERLU PEMERIKSAAN",
        }.get(result_status, result_status)
        pr_number = result.get("pr_number") or "Tidak tersedia"
        status_icon = "✅" if result_status in ("SAP_SUBMITTED", "SAP_SANDBOX_VERIFIED") else "⚠️"
        text = (
            f"{status_icon} <b>HASIL PENGADAAN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏪 <b>Toko:</b> {self._escape(state.store_id)}\n"
            f"🏷️ <b>Barang:</b> {self._escape(state.sku_name or state.sku_id)}\n"
            f"📦 <b>Jumlah:</b> {message.get('quantity', state.final_qty or state.recommended_qty)} Pcs\n"
            f"📄 <b>No. Dokumen SAP:</b> <code>{self._escape(pr_number)}</code>\n"
            f"⚡ <b>Status:</b> {status_copy}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            telegram = self.telegram or TelegramService(db_service=self.db)
            self.telegram = telegram
            if message_id is not None:
                updated = telegram.edit_message_text(chat_id, int(message_id), text)
                if updated:
                    return
            telegram.send_text(chat_id, text)
        except Exception:
            # Telegram notification must not cause SAP SQS redelivery after the
            # SAP state has already been durably recorded.
            logger.exception("Gagal mengirim status Telegram untuk %s", state.request_id)

    @staticmethod
    def _escape(value) -> str:
        import html

        return html.escape(str(value or ""))

    @staticmethod
    def _environment() -> str:
        from backend.src import config

        return config.ENVIRONMENT
