import json
import html
import math
import requests
import backend.src.config as config
from backend.src.models.schema import TelegramApprovalState
from backend.src.services.dynamodb_service import DynamoDBService

class TelegramService:
    def __init__(self, db_service: DynamoDBService = None):
        self.db = db_service or DynamoDBService()
        self.token = config.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def verify_bot(self) -> dict:
        """Memeriksa keabsahan Bot Token Telegram via method getMe."""
        if not self.token:
            return {"status": "NOT_CONFIGURED", "message": "Token Telegram belum disetel"}

        try:
            resp = requests.get(f"{self.base_url}/getMe", timeout=5)
            if resp.status_code == 200 and resp.json().get("ok"):
                bot_info = resp.json().get("result", {})
                return {
                    "status": "CONNECTED",
                    "bot_name": bot_info.get("first_name"),
                    "username": f"@{bot_info.get('username')}"
                }
            return {"status": "ERROR", "message": resp.text}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def send_recommendation_card(
        self,
        chat_id: str,
        request_id: str,
        store_name: str,
        sku_name: str,
        current_stock: int,
        recommended_qty: int,
        confidence: float,
        reasoning: str,
        warnings: list = None,
        daily_burn_rate: float = 0.0,
        threshold: int = None,
        lead_time_days: int = None,
        packaging_multiple: int = 1,
        is_fallback: bool = False,
    ) -> bool:
        """Mengirim kartu notifikasi dengan tombol aksi (Approve, Edit, Reject)."""
        message_text = self.format_recommendation_message(
            store_name=store_name,
            sku_name=sku_name,
            current_stock=current_stock,
            recommended_qty=recommended_qty,
            confidence=confidence,
            reasoning=reasoning,
            warnings=warnings,
            daily_burn_rate=daily_burn_rate,
            threshold=threshold,
            lead_time_days=lead_time_days,
            packaging_multiple=packaging_multiple,
            is_fallback=is_fallback,
        )

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"✅ Setujui ({recommended_qty} Pcs)", "callback_data": f"APPROVE:{request_id}"},
                    {"text": "✏️ Ubah", "callback_data": f"EDIT:{request_id}"}
                ],
                [
                    {"text": "❌ Tolak Pesanan", "callback_data": f"REJECT:{request_id}"}
                ]
            ]
        }

        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(inline_keyboard)
        }

        resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=8)
        return resp.status_code == 200

    @staticmethod
    def format_recommendation_message(
        store_name: str,
        sku_name: str,
        current_stock: int,
        recommended_qty: int,
        confidence: float,
        reasoning: str,
        warnings: list = None,
        daily_burn_rate: float = 0.0,
        threshold: int = None,
        lead_time_days: int = None,
        packaging_multiple: int = 1,
        is_fallback: bool = False,
    ) -> str:
        """Format a concise, non-technical Telegram card for store operators."""
        stock_status = TelegramService._stock_status(
            current_stock=current_stock,
            daily_burn_rate=daily_burn_rate,
            threshold=threshold,
            lead_time_days=lead_time_days,
        )
        stock_suffix = f" ({stock_status})" if stock_status else ""

        package_multiple = max(int(packaging_multiple or 1), 1)
        package_text = ""
        if package_multiple > 1:
            package_count = math.ceil(recommended_qty / package_multiple)
            package_text = f" ({package_count} kemasan @ {package_multiple} Pcs)"

        friendly_warnings = TelegramService._friendly_warnings(warnings, is_fallback)
        warning_text = ""
        if friendly_warnings:
            warning_text = (
                "\n⚠️ <b>Perhatian:</b>\n"
                + "\n".join(f"• {html.escape(item)}" for item in friendly_warnings)
                + "\n"
            )

        return (
            "📦 <b>REKOMENDASI PENGADAAN (AutoReplenish.ai)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏪 <b>Toko:</b> {html.escape(str(store_name))}\n"
            f"🏷️ <b>Barang:</b> {html.escape(str(sku_name))}\n"
            f"📊 <b>Sisa Stok:</b> {current_stock} Pcs{stock_suffix}\n"
            f"🎯 <b>Usulan Order:</b> {recommended_qty} Pcs{package_text}\n"
            f"📈 <b>Keyakinan AI:</b> {confidence * 100:.0f}%\n"
            f"{warning_text}\n"
            "💡 <b>Alasan Pengadaan:</b>\n"
            f"{TelegramService._friendly_reasoning(reasoning)}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Silakan periksa lalu pilih tindakan berikut:"
        )

    @staticmethod
    def _stock_status(
        current_stock: int,
        daily_burn_rate: float,
        threshold: int = None,
        lead_time_days: int = None,
    ) -> str:
        if current_stock <= 0:
            return "Kritis! Stok habis"
        if daily_burn_rate <= 0:
            return "Kritis! Di bawah batas minimum" if threshold is not None and current_stock <= threshold else ""

        hours_remaining = current_stock / daily_burn_rate * 24
        if hours_remaining < 24:
            runway = f"Habis dlm ~{max(1, round(hours_remaining))} jam"
        else:
            days_remaining = hours_remaining / 24
            runway = f"Habis dlm ~{max(1, round(days_remaining))} hari"

        critical = threshold is not None and current_stock <= threshold
        if lead_time_days is not None and hours_remaining < lead_time_days * 24:
            critical = True
        return f"Kritis! {runway}" if critical else runway

    @staticmethod
    def _friendly_reasoning(reasoning: str) -> str:
        lines = []
        for raw_line in str(reasoning or "").splitlines():
            line = raw_line.strip().lstrip("-•").strip()
            if line:
                lines.append(line)
        if not lines:
            lines = ["Kondisi stok dan kebutuhan pengiriman menjadi dasar usulan ini."]
        return "\n".join(f"• {html.escape(line)}" for line in lines[:3])

    @staticmethod
    def _friendly_warnings(warnings: list = None, is_fallback: bool = False) -> list:
        friendly = []
        if is_fallback:
            friendly.append("AI sedang tidak tersedia; usulan dihitung dari kondisi stok dan wajib diperiksa.")
        for warning in warnings or []:
            text = str(warning).strip()
            lowered = text.lower()
            if "fallback" in lowered or "deterministik" in lowered:
                text = "AI sedang tidak tersedia; usulan dihitung dari kondisi stok dan wajib diperiksa."
            elif "confidence" in lowered:
                text = "Keyakinan AI belum tinggi; mohon periksa sebelum menyetujui."
            elif "guardrail" in lowered:
                text = "Jumlah disesuaikan dengan batas keamanan operasional."
            if text and text not in friendly:
                friendly.append(text)
        return friendly[:3]

    def update_message_status(self, chat_id: str, message_id: int, updated_text: str):
        """Memperbarui teks pesan dan melepas tombol setelah interaksi dieksekusi."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": updated_text,
            "parse_mode": "HTML",
        }
        response = requests.post(
            f"{self.base_url}/editMessageText", json=payload, timeout=5
        )
        return response.status_code == 200

    def edit_message_text(self, chat_id: str, message_id: int, text: str) -> bool:
        """Compatibility alias for worker status updates."""
        return self.update_message_status(chat_id, message_id, text)

    def send_text(self, chat_id: str, text: str) -> bool:
        """Send a plain status notification when the original message is unavailable."""
        response = requests.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
        return response.status_code == 200

    def answer_callback(self, callback_query_id: str, alert_text: str = None):
        """Menghentikan indikator loading pada tombol Telegram."""
        payload = {"callback_query_id": callback_query_id}
        if alert_text:
            payload["text"] = alert_text
            payload["show_alert"] = False
        requests.post(f"{self.base_url}/answerCallbackQuery", json=payload, timeout=5)
