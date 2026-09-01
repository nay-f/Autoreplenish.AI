#!/usr/bin/env python3
"""Data Seeding Script for AutoReplenish.ai Local Demo.

Populates SQLite database with 3 stores, 4 SKUs, and 5 inventory baseline records (PRD Section 19.1, 21.5).
"""

import os
import sys

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

from services.local_db import init_db, get_db_connection

DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1181431005")

STORES = [
    {
        "store_id": "STR-001",
        "store_name": "Cabang Sudirman",
        "area_type": "Perkantoran",
        "zone": "JAKARTA_PUSAT",
        "sap_plant": "1000",
        "storage_location": "WH-01",
        "telegram_chat_id": DEFAULT_CHAT_ID,
        "active": 1,
    },
    {
        "store_id": "STR-002",
        "store_name": "Cabang Kemang",
        "area_type": "Perumahan",
        "zone": "JAKARTA_SELATAN",
        "sap_plant": "1000",
        "storage_location": "WH-01",
        "telegram_chat_id": DEFAULT_CHAT_ID,
        "active": 1,
    },
    {
        "store_id": "STR-003",
        "store_name": "Cabang UI Depok",
        "area_type": "Kampus",
        "zone": "DEPOK",
        "sap_plant": "1000",
        "storage_location": "WH-01",
        "telegram_chat_id": DEFAULT_CHAT_ID,
        "active": 1,
    },
]

SKUS = [
    {
        "sku_id": "SKU-10023",
        "sku_name": "Roti Manis Cokelat 100g",
        "category": "Perishable",
        "weather_sensitive": 1,
        "moq": 12,
        "packaging_multiple": 12,
        "base_unit": "PCS",
        "default_lead_time_days": 2,
        "vendor_id": "VEN-009",
    },
    {
        "sku_id": "SKU-20045",
        "sku_name": "Air Mineral 600ml",
        "category": "Non-Perishable",
        "weather_sensitive": 1,
        "moq": 24,
        "packaging_multiple": 24,
        "base_unit": "PCS",
        "default_lead_time_days": 1,
        "vendor_id": "VEN-012",
    },
    {
        "sku_id": "SKU-30067",
        "sku_name": "Susu UHT Full Cream 1L",
        "category": "Perishable",
        "weather_sensitive": 0,
        "moq": 6,
        "packaging_multiple": 6,
        "base_unit": "PCS",
        "default_lead_time_days": 3,
        "vendor_id": "VEN-005",
    },
    {
        "sku_id": "SKU-40089",
        "sku_name": "Mie Instan Goreng",
        "category": "Non-Perishable",
        "weather_sensitive": 0,
        "moq": 40,
        "packaging_multiple": 40,
        "base_unit": "PCS",
        "default_lead_time_days": 2,
        "vendor_id": "VEN-001",
    },
]

INVENTORY = [
    {
        "store_id": "STR-001",
        "sku_id": "SKU-10023",
        "physical_stock": 12,
        "threshold": 20,
        "average_daily_burn_rate": 25,
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-20045",
        "physical_stock": 18,
        "threshold": 30,
        "average_daily_burn_rate": 40,
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-30067",
        "physical_stock": 35,
        "threshold": 15,
        "average_daily_burn_rate": 10,
    },
    {
        "store_id": "STR-002",
        "sku_id": "SKU-40089",
        "physical_stock": 25,
        "threshold": 50,
        "average_daily_burn_rate": 35,
    },
    {
        "store_id": "STR-003",
        "sku_id": "SKU-10023",
        "physical_stock": 8,
        "threshold": 25,
        "average_daily_burn_rate": 30,
    },
]


def main():
    print("=" * 60)
    print("🌱 AUTOREPLENISH.AI — SEEDING DEMO DATA")
    print("=" * 60)

    # Ensure tables exist
    db_path = init_db()

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Seed Stores
        print("\n🏪 Menyimpan Data Toko (3 Toko Pilot):")
        for store in STORES:
            cursor.execute("""
            INSERT OR REPLACE INTO stores (
                store_id, store_name, area_type, zone, sap_plant, storage_location, telegram_chat_id, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                store["store_id"],
                store["store_name"],
                store["area_type"],
                store["zone"],
                store["sap_plant"],
                store["storage_location"],
                store["telegram_chat_id"],
                store["active"],
            ))
            print(f"   • [{store['store_id']}] {store['store_name']} ({store['area_type']} - {store['zone']})")

        # Seed SKUs
        print("\n📋 Menyimpan Data Master SKU (4 SKU):")
        for sku in SKUS:
            cursor.execute("""
            INSERT OR REPLACE INTO skus (
                sku_id, sku_name, category, weather_sensitive, moq, packaging_multiple, base_unit, default_lead_time_days, vendor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sku["sku_id"],
                sku["sku_name"],
                sku["category"],
                sku["weather_sensitive"],
                sku["moq"],
                sku["packaging_multiple"],
                sku["base_unit"],
                sku["default_lead_time_days"],
                sku["vendor_id"],
            ))
            print(f"   • [{sku['sku_id']}] {sku['sku_name']} | Kat: {sku['category']} | MOQ: {sku['moq']}")

        # Seed Inventory
        print("\n📊 Menyimpan Data Stok Awal Toko (5 Record Inventory):")
        for inv in INVENTORY:
            cursor.execute("""
            INSERT OR REPLACE INTO inventory (
                store_id, sku_id, physical_stock, threshold, average_daily_burn_rate
            ) VALUES (?, ?, ?, ?, ?)
            """, (
                inv["store_id"],
                inv["sku_id"],
                inv["physical_stock"],
                inv["threshold"],
                inv["average_daily_burn_rate"],
            ))
            
            is_below = inv["physical_stock"] < inv["threshold"]
            flag = "⚠️ DI BAWAH THRESHOLD (Trigger AI)" if is_below else "✅ SEHAT / DI ATAS THRESHOLD (Skip AI)"
            print(f"   • {inv['store_id']} × {inv['sku_id']}: Stok={inv['physical_stock']}, Min={inv['threshold']} -> {flag}")

        conn.commit()

    print("\n" + "=" * 60)
    print("✅ DATA SEEDING SELESAI DENGAN SUKSES!")
    print("Ringkasan:")
    print("  • 4 item di bawah threshold akan memicu rekomendasi AI di Telegram.")
    print("  • 1 item (STR-001 × SKU-30067 Susu UHT) sehat (35 > 15) dan TIDAK memicu AI.")
    print("\nLangkah selanjutnya: python scripts/03_run_pipeline.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
