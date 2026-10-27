import json
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
        warnings: list = None
    ) -> bool:
        """Mengirim kartu notifikasi dengan tombol aksi (Approve, Edit, Reject)."""
        warning_text = ""
        if warnings:
            warning_text = f"\n⚠️ *Perhatian:* {', '.join(warnings)}\n"

        message_text = (
            f"📦 *REKOMENDASI PENGADAAN (AutoReplenish.ai)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏪 *Toko:* {store_name}\n"
            f"🏷️ *Barang:* {sku_name}\n"
            f"📊 *Sisa Rak:* {current_stock} Pcs\n"
            f"🎯 *Rekomendasi:* `{recommended_qty} Pcs`\n"
            f"📈 *Tingkat Keyakinan:* {confidence * 100:.1f}%\n"
            f"{warning_text}\n"
            f"🧠 *Analisis AI:*\n_{reasoning}_\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Silakan konfirmasi tindakan untuk penerbitan PO/PR SAP:"
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
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(inline_keyboard)
        }

        resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=8)
        return resp.status_code == 200

    def update_message_status(self, chat_id: str, message_id: int, updated_text: str):
        """Memperbarui teks pesan dan melepas tombol setelah interaksi dieksekusi."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": updated_text,
            "parse_mode": "Markdown"
        }
        requests.post(f"{self.base_url}/editMessageText", json=payload, timeout=5)

    def answer_callback(self, callback_query_id: str, alert_text: str = None):
        """Menghentikan indikator loading pada tombol Telegram."""
        payload = {"callback_query_id": callback_query_id}
        if alert_text:
            payload["text"] = alert_text
            payload["show_alert"] = False
        requests.post(f"{self.base_url}/answerCallbackQuery", json=payload, timeout=5)