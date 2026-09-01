#!/usr/bin/env python3
"""Telegram Interactive Callback & Long-Polling Listener for AutoReplenish.ai Demo.

Handles inline button clicks (Approve, Edit, Reject), multi-step conversations,
idempotency protection against duplicate PRs, and Mock SAP S/4HANA integration.
"""

import os
import sys
import time
import math
import logging

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

env_demo = os.path.join(BASE_DIR, ".env")
env_root = os.path.join(os.path.dirname(BASE_DIR), ".env")
if os.path.exists(env_demo):
    load_dotenv(env_demo)
elif os.path.exists(env_root):
    load_dotenv(env_root)
else:
    load_dotenv()

from services.local_db import (
    get_recommendation_by_id,
    update_recommendation_status,
    save_feedback,
    save_audit_log,
    get_store_by_id,
    get_sku_by_id,
)
from services.mock_sap import (
    build_pr_payload,
    create_purchase_requisition,
)
from services.telegram_bot import (
    get_bot_info,
    get_updates,
    send_message,
    send_text_message,
    answer_callback_query,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_listener")

# In-memory user conversational state tracking: chat_id -> state dict
USER_STATES = {}


def handle_approve(chat_id: str, request_id: str, callback_query_id: str):
    """Handle APPROVE button click with idempotency check and SAP PR generation."""
    rec = get_recommendation_by_id(request_id)
    if not rec:
        answer_callback_query(callback_query_id, "❌ Rekomendasi tidak ditemukan.")
        send_text_message(chat_id, f"❌ Rekomendasi dengan ID <code>{request_id}</code> tidak ditemukan.")
        return

    current_status = rec.get("status")

    # 1. IDEMPOTENCY CHECK (PRD 15.6)
    if current_status in ["APPROVED", "PR_CREATED", "EDITED"]:
        pr_info = f" (PR ID: {rec.get('sap_pr_id')})" if rec.get("sap_pr_id") else ""
        answer_callback_query(callback_query_id, "⚠️ Sudah pernah diproses!", show_alert=True)
        send_text_message(
            chat_id,
            f"⚠️ <b>Idempotency Guard:</b> Rekomendasi <code>{request_id}</code> sudah diproses sebelumnya{pr_info}. "
            f"Duplikasi Purchase Requisition dicegah."
        )
        return

    if current_status == "TIMEOUT":
        answer_callback_query(callback_query_id, "⏱️ Rekomendasi kedaluwarsa.")
        send_text_message(chat_id, f"⏱️ Rekomendasi <code>{request_id}</code> telah kedaluwarsa (melewati batas 4 jam).")
        return

    if current_status == "REJECTED":
        answer_callback_query(callback_query_id, "❌ Rekomendasi sudah ditolak.")
        send_text_message(chat_id, f"❌ Rekomendasi <code>{request_id}</code> sebelumnya telah ditolak.")
        return

    # 2. Process Approval
    answer_callback_query(callback_query_id, "✅ Memproses approval...")
    send_text_message(chat_id, "⏳ <b>Rekomendasi disetujui.</b> Sistem sedang menerbitkan Purchase Requisition ke SAP S/4HANA...")

    store = get_store_by_id(rec["store_id"]) or {"store_id": rec["store_id"], "sap_plant": "1000"}
    sku = get_sku_by_id(rec["sku_id"]) or {"sku_id": rec["sku_id"], "sku_name": "Barang", "base_unit": "PCS"}
    
    # Update to APPROVED
    update_recommendation_status(request_id, "APPROVED")

    # Build SAP Payload & Call Mock SAP
    pr_payload = build_pr_payload(store=store, sku=sku, recommendation=rec)
    sap_result = create_purchase_requisition(request_id=request_id, payload=pr_payload)

    if sap_result.get("status") == "SUCCESS":
        pr_id = sap_result["purchase_requisition_id"]
        final_qty = rec.get("final_qty", rec.get("recommended_qty", 1))

        # Update DB state
        update_recommendation_status(
            request_id,
            "PR_CREATED",
            sap_pr_id=pr_id,
            sap_pr_status="APPROVED_CREATED"
        )
        save_feedback({
            "request_id": request_id,
            "store_id": rec["store_id"],
            "sku_id": rec["sku_id"],
            "action": "APPROVED",
            "reason": "Approved by store manager via Telegram button",
            "original_qty": rec["recommended_qty"],
            "final_qty": final_qty,
        })
        save_audit_log({
            "request_id": request_id,
            "event_type": "SAP_PR_CREATED",
            "payload": sap_result,
        })

        success_msg = (
            f"✅ <b>Purchase Requisition berhasil dibuat di SAP S/4HANA!</b>\n\n"
            f"📄 <b>PR ID:</b> <code>{pr_id}</code>\n"
            f"🏪 <b>Toko:</b> {store.get('store_name', store.get('store_id'))}\n"
            f"📋 <b>SKU:</b> {sku.get('sku_name', sku.get('sku_id'))}\n"
            f"📦 <b>Jumlah Dipesan:</b> {final_qty} {sku.get('base_unit', 'Pcs')}\n"
            f"🕒 <b>Waktu:</b> {sap_result.get('timestamp', '-')}"
        )
        send_text_message(chat_id, success_msg)
        logger.info(f"Successfully processed approval for {request_id} -> {pr_id}")
    else:
        update_recommendation_status(request_id, "FAILED_SAP", sap_pr_status="CREATION_FAILED")
        send_text_message(chat_id, f"❌ Gagal membuat Purchase Requisition di SAP: {sap_result.get('message')}")


def handle_edit_init(chat_id: str, request_id: str, callback_query_id: str):
    """Initiate interactive quantity edit flow."""
    rec = get_recommendation_by_id(request_id)
    if not rec:
        answer_callback_query(callback_query_id, "❌ Rekomendasi tidak ditemukan.")
        return

    if rec.get("status") != "PENDING_APPROVAL":
        answer_callback_query(callback_query_id, f"⚠️ Status tidak dapat diedit ({rec.get('status')})", show_alert=True)
        return

    sku = get_sku_by_id(rec["sku_id"]) or {}
    sku_name = sku.get("sku_name", rec["sku_id"])
    moq = sku.get("moq", 1)
    pkg = sku.get("packaging_multiple", 1)

    answer_callback_query(callback_query_id, "✏️ Mode edit jumlah aktif.")

    USER_STATES[str(chat_id)] = {
        "state": "WAITING_QTY",
        "request_id": request_id,
        "sku": sku,
        "recommendation": rec,
    }

    prompt_text = (
        f"✏️ <b>Ubah Jumlah Pemesanan</b>\n\n"
        f"📋 SKU: <b>{sku_name}</b>\n"
        f"💡 Rekomendasi AI: <b>{rec.get('recommended_qty')} Pcs</b>\n"
        f"📦 MOQ: <b>{moq} Pcs</b> | Kelipatan Kemasan: <b>{pkg} Pcs</b>\n\n"
        f"Silakan ketik <b>angka quantity baru</b> yang Anda inginkan (contoh: <code>{moq * 2}</code>):"
    )
    send_text_message(chat_id, prompt_text)


def handle_reject_init(chat_id: str, request_id: str, callback_query_id: str):
    """Initiate interactive rejection with reason prompt."""
    rec = get_recommendation_by_id(request_id)
    if not rec:
        answer_callback_query(callback_query_id, "❌ Rekomendasi tidak ditemukan.")
        return

    if rec.get("status") != "PENDING_APPROVAL":
        answer_callback_query(callback_query_id, f"⚠️ Status saat ini: {rec.get('status')}", show_alert=True)
        return

    answer_callback_query(callback_query_id, "❌ Mode penolakan aktif.")

    USER_STATES[str(chat_id)] = {
        "state": "WAITING_REASON",
        "request_id": request_id,
        "recommendation": rec,
    }

    send_text_message(
        chat_id,
        f"❌ <b>Tolak Rekomendasi [{rec.get('request_id')}]</b>\n\n"
        f"Mohon tuliskan <b>alasan penolakan</b> rekomendasi ini (contoh: <i>'Stok gudang masih cukup untuk akhir pekan'</i>):"
    )


def handle_text_message(chat_id: str, text: str):
    """Handle incoming text messages based on active conversational state."""
    state_data = USER_STATES.get(str(chat_id))
    raw_text = text.strip()

    if not state_data:
        send_text_message(
            chat_id,
            "ℹ️ Tidak ada aksi yang sedang menunggu.\nSilakan gunakan tombol pada kartu rekomendasi stok."
        )
        return

    current_state = state_data.get("state")
    request_id = state_data.get("request_id")
    rec = state_data.get("recommendation", {})

    # 1. State: WAITING_QTY
    if current_state == "WAITING_QTY":
        if raw_text.upper() in ["BATAL", "CANCEL"]:
            del USER_STATES[str(chat_id)]
            send_text_message(chat_id, "❌ Perubahan jumlah dibatalkan.")
            return

        try:
            new_qty = int(raw_text)
            if new_qty <= 0:
                send_text_message(chat_id, "⚠️ Jumlah harus berupa angka bulat positif (> 0). Silakan coba lagi:")
                return

            sku = state_data.get("sku", {})
            moq = sku.get("moq", 1)
            pkg = sku.get("packaging_multiple", 1)
            warnings = []

            if new_qty < moq:
                warnings.append(f"⚠️ Angka {new_qty} Pcs di bawah MOQ ({moq} Pcs).")

            if pkg > 1 and (new_qty % pkg != 0):
                nearest = int(math.ceil(new_qty / pkg) * pkg)
                warnings.append(f"⚠️ Angka {new_qty} Pcs bukan kelipatan kemasan ({pkg} Pcs). Disarankan: {nearest} Pcs.")

            warn_str = "\n".join(warnings) + "\n\n" if warnings else ""

            state_data["state"] = "CONFIRM_QTY"
            state_data["pending_qty"] = new_qty
            USER_STATES[str(chat_id)] = state_data

            confirm_text = (
                f"📝 <b>Konfirmasi Perubahan Jumlah</b>\n\n"
                f"{warn_str}"
                f"Jumlah Baru: <b>{new_qty} Pcs</b> (Sebelumnya: {rec.get('recommended_qty')} Pcs)\n\n"
                f"Ketik <b>YA</b> untuk konfirmasi & kirim ke SAP S/4HANA, atau ketik <b>BATAL</b> untuk membatalkan."
            )
            send_text_message(chat_id, confirm_text)

        except ValueError:
            send_text_message(chat_id, "⚠️ Masukan tidak valid. Harap ketik angka bulat (misal: <code>24</code>) atau ketik <b>BATAL</b>.")

    # 2. State: CONFIRM_QTY
    elif current_state == "CONFIRM_QTY":
        if raw_text.upper() in ["YA", "Y", "YES", "OK"]:
            new_qty = state_data.get("pending_qty", rec.get("recommended_qty", 1))
            store = get_store_by_id(rec["store_id"]) or {"store_id": rec["store_id"], "sap_plant": "1000"}
            sku = state_data.get("sku") or get_sku_by_id(rec["sku_id"]) or {"sku_id": rec["sku_id"], "sku_name": "Barang", "base_unit": "PCS"}

            update_recommendation_status(request_id, "EDITED", final_qty=new_qty)

            # Build PR with modified qty
            pr_payload = build_pr_payload(
                store=store,
                sku=sku,
                recommendation={"final_qty": new_qty, "recommended_qty": rec.get("recommended_qty")}
            )
            sap_result = create_purchase_requisition(request_id=request_id, payload=pr_payload)

            if sap_result.get("status") == "SUCCESS":
                pr_id = sap_result["purchase_requisition_id"]
                update_recommendation_status(
                    request_id,
                    "PR_CREATED",
                    final_qty=new_qty,
                    sap_pr_id=pr_id,
                    sap_pr_status="EDITED_CREATED"
                )
                save_feedback({
                    "request_id": request_id,
                    "store_id": rec["store_id"],
                    "sku_id": rec["sku_id"],
                    "action": "EDITED",
                    "reason": f"Quantity edited by user from {rec.get('recommended_qty')} to {new_qty}",
                    "original_qty": rec.get("recommended_qty"),
                    "final_qty": new_qty,
                })
                save_audit_log({
                    "request_id": request_id,
                    "event_type": "QUANTITY_EDITED_AND_PR_CREATED",
                    "payload": {
                        "original_qty": rec.get("recommended_qty"),
                        "final_qty": new_qty,
                        "sap_result": sap_result,
                    }
                })

                send_text_message(
                    chat_id,
                    f"✅ <b>Perubahan Diterapkan & Purchase Requisition Diterbitkan!</b>\n\n"
                    f"📄 <b>PR ID:</b> <code>{pr_id}</code>\n"
                    f"📋 <b>SKU:</b> {sku.get('sku_name', rec['sku_id'])}\n"
                    f"📦 <b>Jumlah Final:</b> {new_qty} {sku.get('base_unit', 'Pcs')}\n"
                    f"🔄 <b>Rekomendasi Awal AI:</b> {rec.get('recommended_qty')} Pcs"
                )
            else:
                send_text_message(chat_id, f"❌ Gagal mengirim ke SAP: {sap_result.get('message')}")

            del USER_STATES[str(chat_id)]

        elif raw_text.upper() in ["BATAL", "CANCEL", "TIDAK", "NO"]:
            del USER_STATES[str(chat_id)]
            send_text_message(chat_id, "❌ Perubahan jumlah dibatalkan.")
        else:
            send_text_message(chat_id, "Ketik <b>YA</b> untuk konfirmasi atau <b>BATAL</b> untuk membatalkan:")

    # 3. State: WAITING_REASON
    elif current_state == "WAITING_REASON":
        reason = raw_text
        update_recommendation_status(request_id, "REJECTED")
        save_feedback({
            "request_id": request_id,
            "store_id": rec["store_id"],
            "sku_id": rec["sku_id"],
            "action": "REJECTED",
            "reason": reason,
            "original_qty": rec.get("recommended_qty"),
            "final_qty": 0,
        })
        save_audit_log({
            "request_id": request_id,
            "event_type": "RECOMMENDATION_REJECTED",
            "payload": {
                "request_id": request_id,
                "reason": reason,
                "original_rec": rec,
            }
        })

        send_text_message(
            chat_id,
            f"❌ <b>Rekomendasi Dibatalkan</b>\n\n"
            f"Alasan: <i>\"{reason}\"</i>\n"
            f"Feedback telah disimpan untuk perbaikan penalaran agen berikutnya (Continuous Learning)."
        )
        del USER_STATES[str(chat_id)]


def main():
    print("=" * 65)
    print("🤖 AUTOREPLENISH.AI — TELEGRAM INTERACTIVE LISTENER")
    print("=" * 65)

    try:
        bot_info = get_bot_info()
        print(f"✅ Bot Terhubung: @{bot_info.get('username')}")
        print("📡 Mode: Long Polling aktif (mendengarkan klik tombol & balasan pesan)...")
        print("💡 Tekan Ctrl + C untuk menghentikan listener.\n")
    except Exception as e:
        print(f"❌ Gagal memulai bot listener: {e}")
        sys.exit(1)

    last_update_id = 0

    try:
        while True:
            updates = get_updates(offset=last_update_id + 1, timeout=20)
            for update in updates:
                last_update_id = update["update_id"]

                # 1. Handle Callback Query (Button click)
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb["id"]
                    data = cb.get("data", "")
                    sender_chat_id = str(cb["message"]["chat"]["id"])

                    logger.info(f"Received Callback Query: {data} from Chat {sender_chat_id}")

                    if ":" in data:
                        action, req_id = data.split(":", 1)
                        if action == "APPROVE":
                            handle_approve(sender_chat_id, req_id, cb_id)
                        elif action == "EDIT":
                            handle_edit_init(sender_chat_id, req_id, cb_id)
                        elif action == "REJECT":
                            handle_reject_init(sender_chat_id, req_id, cb_id)
                        else:
                            answer_callback_query(cb_id, "Aksi tidak dikenal.")

                # 2. Handle Text Messages
                elif "message" in update:
                    msg = update["message"]
                    sender_chat_id = str(msg["chat"]["id"])
                    msg_text = msg.get("text", "")

                    if msg_text:
                        logger.info(f"Received Text Message: '{msg_text}' from Chat {sender_chat_id}")
                        handle_text_message(sender_chat_id, msg_text)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\n🛑 Telegram Listener dihentikan dengan aman.")
        sys.exit(0)


if __name__ == "__main__":
    main()
