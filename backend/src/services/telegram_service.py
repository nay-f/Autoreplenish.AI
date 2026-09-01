"""Telegram Bot Service for Human-in-the-Loop Replenishment Approval.

Implements PRD Section 11.7, 14.4, and 27 (Card formatting and callback keyboard).
"""

import json
import logging
from typing import Dict, Any, Optional, List
from ..config import logger
from ..models.schema import (
    AggregationContext,
    AIRecommendationOutput,
)

class TelegramService:
    """Manages Telegram message formatting, button generation, and dispatch."""

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token
        self._sent_messages: List[Dict[str, Any]] = []

    def format_recommendation_card(
        self,
        context: AggregationContext,
        recommendation: AIRecommendationOutput,
        final_qty: int,
        request_id: str
    ) -> str:
        """Format rich card conforming to Section 27 sample card."""
        store = context.store
        sku = context.sku
        weather = context.external_context.weather
        calendar = context.external_context.calendar

        packaging_desc = f" ({final_qty // sku.packaging_multiple} Dus)" if sku.packaging_multiple > 1 and final_qty >= sku.packaging_multiple else ""

        card = (
            f"📦 *AUTOREPLENISH.AI — Rekomendasi Replenishment Stok*\n\n"
            f"🏪 *Toko:* {store.store_name} ({store.area_type})\n"
            f"🏷️ *SKU:* {sku.sku_name} ({sku.category})\n\n"
            f"📊 *Stok Fisik:* {sku.physical_stock} {sku.base_unit}\n"
            f"🎯 *Threshold:* {sku.threshold} {sku.base_unit}\n"
            f"🚚 *Lead Time:* {sku.lead_time_days} Hari\n"
            f"🌦️ *Cuaca:* {weather.condition} ({calendar.day_type})\n\n"
            f"🧠 *Analisis Agent (AWS Bedrock):*\n"
            f"_{recommendation.reasoning_narrative}_\n\n"
            f"💡 *Rekomendasi:* *{final_qty} {sku.base_unit}*{packaging_desc} — *Normal:* {recommendation.normal_qty} {sku.base_unit}\n"
            f"Ref: `{request_id}`"
        )
        return card

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

    def send_recommendation_card(
        self,
        chat_id: str,
        context: AggregationContext,
        recommendation: AIRecommendationOutput,
        final_qty: int,
        request_id: str
    ) -> Dict[str, Any]:
        """Send or simulate sending recommendation card to Telegram."""
        text = self.format_recommendation_card(context, recommendation, final_qty, request_id)
        reply_markup = self.get_inline_keyboard(request_id)

        message_record = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "request_id": request_id,
            "message_id": f"msg_{len(self._sent_messages) + 1001}"
        }
        self._sent_messages.append(message_record)
        logger.info(f"Dispatched Telegram recommendation card for request {request_id} to chat {chat_id}")
        return message_record
