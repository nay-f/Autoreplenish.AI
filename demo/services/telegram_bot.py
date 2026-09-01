"""Telegram Bot Integration Service for AutoReplenish.ai Demo.

Communicates with real Telegram Bot API via HTTPS (requests) using long polling mode.
Implements card formatting (PRD Section 27) and callback queries (PRD Section 14.4).
"""

import os
import logging
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger("telegram_bot")


def get_bot_token() -> str:
    """Get Telegram Bot Token from environment variable."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    return token


def get_api_url(method: str) -> str:
    """Build full Telegram Bot API endpoint URL."""
    token = get_bot_token()
    return f"https://api.telegram.org/bot{token}/{method}"


def get_bot_info() -> Dict[str, Any]:
    """Verify bot token and fetch bot profile from Telegram getMe API."""
    url = get_api_url("getMe")
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if not data.get("ok"):
            raise ValueError(f"Telegram API Error: {data.get('description', 'Unknown error')}")
        return data["result"]
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        raise


def send_message(
    chat_id: str,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: str = "HTML"
) -> Dict[str, Any]:
    """Send text message with optional inline keyboard to Telegram chat."""
    url = get_api_url("sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        if not data.get("ok"):
            raise ValueError(f"Telegram sendMessage failed: {data.get('description')}")
        return data["result"]
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")
        raise


def send_text_message(chat_id: str, text: str) -> Dict[str, Any]:
    """Convenience helper to send plain text / markdown messages."""
    return send_message(chat_id=chat_id, text=text, parse_mode="HTML")


def send_recommendation_card(
    chat_id: str,
    recommendation: Dict[str, Any],
    store: Dict[str, Any],
    sku: Dict[str, Any],
    weather: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format and send rich recommendation card with inline keyboard buttons (PRD Section 27).
    """
    request_id = recommendation["request_id"]
    store_name = store.get("store_name", "Toko")
    area_type = store.get("area_type", "Umum")
    
    sku_name = sku.get("sku_name", "Barang")
    category = sku.get("category", "Non-Perishable")
    lead_time = sku.get("default_lead_time_days", sku.get("lead_time_days", 1))

    physical_stock = recommendation.get("physical_stock", store.get("physical_stock", 0))
    threshold = recommendation.get("threshold", store.get("threshold", 0))
    
    # If not present at top level, check input context or inventory
    input_ctx = recommendation.get("input_context", {})
    if isinstance(input_ctx, dict) and "inventory" in input_ctx:
        physical_stock = input_ctx["inventory"].get("physical_stock", physical_stock)
        threshold = input_ctx["inventory"].get("threshold", threshold)

    weather_condition = weather.get("condition", "Normal")
    reasoning_narrative = recommendation.get("reasoning_narrative", "-")
    recommended_qty = recommendation.get("recommended_qty", 0)
    normal_qty = recommendation.get("normal_qty", 0)
    
    confidence_val = recommendation.get("confidence_score", 0.85)
    confidence_pct = int(confidence_val * 100) if confidence_val <= 1.0 else int(confidence_val)
    risk_level = str(recommendation.get("risk_level", "medium")).upper()

    card_text = (
        f"📦 <b>AUTOREPLENISH.AI — Rekomendasi Replenishment Stok</b>\n\n"
        f"🏪 Toko: <b>{store_name}</b> (Area {area_type})\n"
        f"📋 SKU: <b>{sku_name}</b> ({category})\n"
        f"📊 Stok Fisik: <b>{physical_stock} Pcs</b>\n"
        f"📏 Threshold: <b>{threshold} Pcs</b>\n"
        f"🚚 Lead Time: <b>{lead_time} Hari</b>\n"
        f"🌤️ Cuaca: <b>{weather_condition}</b>\n\n"
        f"🧠 <b>Analisis Agent (AWS Bedrock):</b>\n"
        f"<i>\"{reasoning_narrative}\"</i>\n\n"
        f"💡 <b>Rekomendasi: {recommended_qty} Pcs</b> — Normal: {normal_qty} Pcs\n"
        f"📊 Confidence: <b>{confidence_pct}%</b> | Risk: <b>{risk_level}</b>"
    )

    warnings = recommendation.get("warnings", [])
    if isinstance(warnings, list) and len(warnings) > 0:
        warning_bullets = "\n".join([f"• {w}" for w in warnings])
        card_text += f"\n\n⚠️ <b>Warnings:</b>\n{warning_bullets}"

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve & Kirim ke SAP",
                    "callback_data": f"APPROVE:{request_id}",
                }
            ],
            [
                {
                    "text": "✏️ Ubah Jumlah",
                    "callback_data": f"EDIT:{request_id}",
                },
                {
                    "text": "❌ Tolak",
                    "callback_data": f"REJECT:{request_id}",
                },
            ],
        ]
    }

    return send_message(chat_id=chat_id, text=card_text, reply_markup=reply_markup)


def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False
) -> bool:
    """Acknowledge button click from Telegram inline keyboard."""
    url = get_api_url("answerCallbackQuery")
    payload = {
        "callback_query_id": callback_query_id,
        "text": text or "",
        "show_alert": show_alert,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json().get("ok", False)
    except Exception as e:
        logger.warning(f"Error answering callback query: {e}")
        return False


def edit_message_text(
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: str = "HTML"
) -> Dict[str, Any]:
    """Edit existing Telegram message content / buttons."""
    url = get_api_url("editMessageText")
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=15)
        return response.json().get("result", {})
    except Exception as e:
        logger.error(f"Error editing message {message_id}: {e}")
        return {}


def get_updates(offset: Optional[int] = None, timeout: int = 30) -> List[Dict[str, Any]]:
    """Long polling to fetch incoming updates from Telegram."""
    url = get_api_url("getUpdates")
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(url, params=params, timeout=timeout + 5)
        data = response.json()
        if data.get("ok"):
            return data.get("result", [])
        return []
    except requests.exceptions.Timeout:
        return []
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return []
