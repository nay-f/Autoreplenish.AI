#!/usr/bin/env python3
"""AI Replenishment Pipeline Orchestrator for AutoReplenish.ai Local Demo.

Simulates EventBridge Scheduled Rule -> Lambda Orchestrator flow (PRD Section 9, 11.1-11.7).
Aggregates store inventory, fetches weather and calendar effects, invokes Bedrock reasoning,
persists recommendations to SQLite, and delivers rich interactive Telegram cards.
"""

import os
import sys
import uuid
import time
from datetime import datetime, timezone, timedelta

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
    get_all_stores,
    get_priority_skus,
    get_store_by_id,
    get_sku_by_id,
    get_inventory,
    save_recommendation,
    update_recommendation_status,
    save_audit_log,
)
from services.mock_weather import get_weather_for_zone
from services.mock_bedrock import invoke_bedrock, get_prompt_info
from services.telegram_bot import get_bot_info, send_recommendation_card


def main():
    now_dt = datetime.now()
    now_utc = datetime.now(timezone.utc)
    run_id = f"RUN-DEMO-{now_dt.strftime('%Y%m%d-%H%M%S')}"

    print("=" * 65)
    print(f"⚡ AUTOREPLENISH.AI — AI REPLENISHMENT PIPELINE RUN")
    print(f"🆔 Run ID: {run_id}")
    print(f"🕒 Timestamp: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # 1. Verify Telegram Bot
    print("\n🔍 1. Memeriksa Koneksi Telegram Bot...")
    try:
        bot_info = get_bot_info()
        bot_uname = bot_info.get("username", "Unknown")
        print(f"   ✅ Bot Terhubung: @{bot_uname}")
    except Exception as e:
        print(f"   ❌ Gagal menghubungi Telegram Bot API: {e}")
        print("   Pastikan TELEGRAM_BOT_TOKEN di .env sudah benar.")
        sys.exit(1)

    # 2. Get Active Stores
    print("\n🏪 2. Memuat Daftar Toko Aktif...")
    stores = get_all_stores(active_only=True)
    print(f"   Ditemukan {len(stores)} toko aktif.")

    # 3. Calendar Context
    day_type = "Weekend" if now_dt.weekday() >= 5 else "Weekday"
    calendar_ctx = {
        "date": now_dt.strftime("%Y-%m-%d"),
        "day_name": now_dt.strftime("%A"),
        "day_type": day_type,
        "is_holiday": False,
        "is_payday": now_dt.day in [25, 26, 27, 28, 29, 30, 31, 1],
    }
    print(f"   📅 Kalender: {calendar_ctx['day_name']} ({day_type}) | Payday: {calendar_ctx['is_payday']}")

    total_recommendations = 0
    total_cards_sent = 0

    # 4. Process Each Store
    print("\n🚀 3. Memproses Evaluasi Stok per Toko:")
    for store in stores:
        store_id = store["store_id"]
        store_name = store["store_name"]
        zone = store["zone"]
        chat_id = store.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")

        print(f"\n   --------------------------------------------------")
        print(f"   🏪 [{store_id}] {store_name} ({store['area_type']} | Zone: {zone})")

        # Weather for store zone
        weather_ctx = get_weather_for_zone(zone)
        print(f"      🌤️ Cuaca: {weather_ctx['condition']} ({weather_ctx['temperature_c']}°C, Hujan: {int(weather_ctx['rain_probability']*100)}%)")

        # Priority SKUs (Stock < Threshold)
        priority_skus = get_priority_skus(store_id)
        if not priority_skus:
            print("      ✅ Seluruh SKU di toko ini dalam kondisi stok sehat (di atas threshold).")
            continue

        print(f"      ⚠️ Ditemukan {len(priority_skus)} SKU di bawah threshold:")

        for item in priority_skus:
            sku_id = item["sku_id"]
            sku_name = item["sku_name"]
            category = item["category"]
            p_stock = item["physical_stock"]
            thresh = item["threshold"]
            burn_rate = item["average_daily_burn_rate"]
            lead_time = item["default_lead_time_days"]

            print(f"\n      👉 Evaluasi AI: [{sku_id}] {sku_name} ({category})")
            print(f"         Stok: {p_stock} Pcs | Threshold: {thresh} Pcs | Burn Rate: {burn_rate}/hari | Lead Time: {lead_time} hari")

            # Build Full Aggregation Context
            context_payload = {
                "run_id": run_id,
                "store": store,
                "sku": item,
                "inventory": {
                    "physical_stock": p_stock,
                    "threshold": thresh,
                    "average_daily_burn_rate": burn_rate,
                },
                "weather": weather_ctx,
                "calendar": calendar_ctx,
            }

            # Invoke Bedrock Reasoning
            ai_output = invoke_bedrock(context_payload)
            prompt_info = get_prompt_info()

            # Generate Request ID and Expiry
            req_random = uuid.uuid4().hex[:6].upper()
            request_id = f"REQ-{now_dt.strftime('%Y%m%d')}-{req_random}"
            expires_at = (now_utc + timedelta(hours=4)).isoformat()

            # Record Recommendation in DB
            rec_record = {
                "request_id": request_id,
                "run_id": run_id,
                "store_id": store_id,
                "sku_id": sku_id,
                "recommended_qty": ai_output["recommended_qty"],
                "normal_qty": ai_output["normal_qty"],
                "adjusted_qty_before_moq": ai_output["adjusted_qty_before_moq"],
                "moq_applied": ai_output["moq_applied"],
                "packaging_multiple_applied": ai_output["packaging_multiple_applied"],
                "final_qty": ai_output["recommended_qty"],
                "confidence_score": ai_output["confidence_score"],
                "risk_level": ai_output["risk_level"],
                "reasoning_narrative": ai_output["reasoning_narrative"],
                "key_factors": ai_output["key_factors"],
                "warnings": ai_output["warnings"],
                "status": "PENDING_APPROVAL",
                "prompt_version": prompt_info.get("prompt_version", "v1.0"),
                "ai_output": ai_output,
                "input_context": context_payload,
                "expires_at": expires_at,
                "created_at": now_utc.isoformat(),
            }

            save_recommendation(rec_record)
            save_audit_log({
                "request_id": request_id,
                "event_type": "RECOMMENDATION_GENERATED",
                "payload": {
                    "ai_output": ai_output,
                    "prompt_info": prompt_info,
                    "context": context_payload,
                }
            })
            total_recommendations += 1

            print(f"         💡 Rekomendasi AI: {ai_output['recommended_qty']} Pcs (Normal: {ai_output['normal_qty']} Pcs)")
            print(f"         📊 Confidence: {int(ai_output['confidence_score']*100)}% | Risk: {ai_output['risk_level'].upper()}")
            print(f"         📝 Penalaran: \"{ai_output['reasoning_narrative']}\"")

            # Send Telegram Card
            if chat_id:
                try:
                    tg_resp = send_recommendation_card(
                        chat_id=chat_id,
                        recommendation=rec_record,
                        store=store,
                        sku=item,
                        weather=weather_ctx,
                    )
                    msg_id = tg_resp.get("message_id")
                    if msg_id:
                        update_recommendation_status(request_id, "PENDING_APPROVAL", telegram_message_id=str(msg_id))
                    print(f"         📤 Card Telegram Terkirim! (Msg ID: {msg_id})")
                    total_cards_sent += 1
                except Exception as tg_err:
                    print(f"         ⚠️ Gagal mengirim card Telegram: {tg_err}")
            
            # Gentle throttle to avoid rate limiting
            time.sleep(0.5)

    print("\n" + "=" * 65)
    print("🎉 PIPELINE RUN SELESAI!")
    print(f"  • Total Toko Diproses       : {len(stores)}")
    print(f"  • Total Rekomendasi Dibuat  : {total_recommendations}")
    print(f"  • Total Pesan Telegram Card : {total_cards_sent}")
    print("\n📱 Silakan cek Telegram Anda untuk melihat kartu rekomendasi.")
    print("Langkah selanjutnya:")
    print("  1. Buka terminal baru dan jalankan Telegram Listener:")
    print("     python scripts/04_telegram_listener.py")
    print("  2. Klik tombol Approve / Edit / Reject di Telegram untuk menguji alur interaksi.")
    print("=" * 65)


if __name__ == "__main__":
    main()
