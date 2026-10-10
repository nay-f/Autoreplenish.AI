"""Telegram Bot Service for Human-in-the-Loop Replenishment Approval.

Implements PRD Section 11.7, 14.4, and 27:
- Rich recommendation card rendering (parse_mode Markdown).
- Inline keyboard with ``APPROVE:{request_id}`` / ``EDIT:{request_id}`` /
  ``REJECT:{request_id}`` callback data.
- Real HTTPS calls to the Telegram Bot API (sendMessage, answerCallbackQuery,
  editMessageText) so the card actually reaches the store manager.

The bot token is resolved from AWS Secrets Manager (infra/secrets.tf) and is
never embedded in the frontend or the repository.
"""

from typing import Any, Dict, Optional

import requests

from ..config import (
    logger,
    TELEGRAM_SECRET_NAME,
    TELEGRAM_API_BASE_URL,
    TELEGRAM_TIMEOUT_SECONDS,
    TELEGRAM_BOT_TOKEN_FALLBACK,
)
from ..models.schema import (
    AggregationContext,
    AIRecommendationOutput,
)
from .secrets_service import SecretManagerService

PARSE_MODE = "Markdown"


class TelegramService:
    """Manages Telegram message formatting, keyboards, and real dispatch."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        secret_service: Optional[SecretManagerService] = None,
        http_client: Optional[Any] = None,
    ):
        """
        Args:
            bot_token: Explicit token. Resolved from Secrets Manager when omitted.
            secret_service: Injectable SecretManagerService (for tests).
            http_client: Injectable object exposing ``.post(url, json, timeout)``.
        """
        self._bot_token = bot_token
        self._secret_service = secret_service
        self._http = http_client or requests

    # ---------------------------------------------------------
    # Token / API plumbing
    # ---------------------------------------------------------
    def _resolve_bot_token(self) -> str:
        if self._bot_token:
            return self._bot_token
        if self._secret_service is None:
            self._secret_service = SecretManagerService()
        token = self._secret_service.get_telegram_bot_token(TELEGRAM_SECRET_NAME)
        if not token:
            token = TELEGRAM_BOT_TOKEN_FALLBACK
        self._bot_token = token
        return token

    def _api_url(self, method: str) -> str:
        base = (TELEGRAM_API_BASE_URL or "https://api.telegram.org").rstrip("/")
        return f"{base}/bot{self._resolve_bot_token()}/{method}"

    def _post(self, method: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST to the Bot API. Returns the ``result`` object or None on failure.

        Dispatch failures are logged and swallowed: a Telegram outage must never
        abort the replenishment run or lose the audit record.
        """
        url = self._api_url(method)
        try:
            response = self._http.post(url, json=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
            data = response.json() if response.content else {}
            if not data.get("ok"):
                logger.error(
                    f"Telegram {method} failed: HTTP {response.status_code} "
                    f"{data.get('description', 'unknown error')}"
                )
                return None
            return data.get("result")
        except Exception as e:
            logger.error(f"Telegram {method} request error: {e}")
            return None

    # ---------------------------------------------------------
    # Card rendering (PRD Section 27)
    # ---------------------------------------------------------
    def format_recommendation_card(
        self,
        context: AggregationContext,
        recommendation: AIRecommendationOutput,
        final_qty: int,
        request_id: str
    ) -> str:
        """Format the rich card conforming to Section 27."""
        store = context.store
        sku = context.sku
        weather = context.external_context.weather
        calendar = context.external_context.calendar

        packaging_desc = (
            f" ({final_qty // sku.packaging_multiple} Dus)"
            if sku.packaging_multiple > 1 and final_qty >= sku.packaging_multiple else ""
        )

        expired_note = ""
        if sku.shelf_life_days <= 3 and final_qty > 0:
            expired_note = f"\n⏳ *Shelf Life:* {sku.shelf_life_days} hari"

        fallback_warning = ""
        if recommendation.is_fallback:
            fallback_warning = (
                "\n\n⚠️ *Catatan:* Model AI tidak dapat dihubungi. "
                "Angka ini dihitung atas dasar aturan konservatif internal."
            )

        return (
            f"📦 *AUTOREPLENISH.AI — Rekomendasi Replenishment Stok*\n\n"
            f"🏪 *Toko:* {store.store_name} ({store.area_type})\n"
            f"🏷️ *SKU:* {sku.sku_name} ({sku.category})\n\n"
            f"📊 *Stok Fisik:* {sku.physical_stock} {sku.base_unit}\n"
            f"🎯 *Threshold:* {sku.threshold} {sku.base_unit}\n"
            f"🚚 *Lead Time:* {sku.lead_time_days} Hari{expired_note}\n"
            f"🌦️ *Cuaca:* {weather.condition} ({calendar.day_type})\n\n"
            f"🧠 *Analisis Agent (AWS Bedrock):*\n"
            f"_{recommendation.reasoning_narrative}_\n\n"
            f"💡 *Rekomendasi:* *{final_qty} {sku.base_unit}*{packaging_desc} — "
            f"*Normal:* {recommendation.normal_qty} {sku.base_unit}\n"
            f"Ref: `{request_id}`"
            f"{fallback_warning}"
        )

    def get_inline_keyboard(self, request_id: str) -> Dict[str, Any]:
        """Generate inline callback buttons: Approve, Edit, Reject."""
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Approve & Kirim ke SAP",
                        "callback_data": f"APPROVE:{request_id}"
                    }
                ],
                [
                    {
                        "text": "✏️ Ubah Jumlah",
                        "callback_data": f"EDIT:{request_id}"
                    },
                    {
                        "text": "❌ Tolak",
                        "callback_data": f"REJECT:{request_id}"
                    }
                ]
            ]
        }

    # ---------------------------------------------------------
    # Bot API methods (PRD Section 14.4)
    # ---------------------------------------------------------
    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = PARSE_MODE
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._post("sendMessage", payload)

    def send_recommendation_card(
        self,
        chat_id: str,
        context: AggregationContext,
        recommendation: AIRecommendationOutput,
        final_qty: int,
        request_id: str
    ) -> Dict[str, Any]:
        """Dispatch the recommendation card to a store manager's chat."""
        text = self.format_recommendation_card(context, recommendation, final_qty, request_id)
        reply_markup = self.get_inline_keyboard(request_id)

        result = self.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

        message_record: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "request_id": request_id,
            "message_id": None,
            "delivered": False,
        }

        if result and result.get("message_id") is not None:
            message_record["message_id"] = str(result["message_id"])
            message_record["delivered"] = True
            logger.info(
                f"Telegram card delivered for request {request_id} "
                f"(chat {chat_id}, message_id {result['message_id']})"
            )
        else:
            # Card was not delivered: strip buttons so no stale callback can be
            # clicked against a request that was never created.
            message_record["reply_markup"] = None
            message_record["error"] = "Telegram sendMessage failed"

        return message_record

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
        show_alert: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Acknowledge a button click so the Telegram client stops its spinner."""
        if not callback_query_id:
            return None
        return self._post("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        })

    def edit_message_text(
        self,
        chat_id: str,
        message_id: Optional[str],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = PARSE_MODE
    ) -> Optional[Dict[str, Any]]:
        """Update the original card once the approval state changes."""
        if message_id in (None, ""):
            logger.info("No telegram_message_id recorded; skipping editMessageText")
            return None
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": int(message_id) if str(message_id).isdigit() else message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._post("editMessageText", payload)
