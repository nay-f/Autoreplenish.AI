#!/usr/bin/env python3
"""Database Initialization Script for AutoReplenish.ai Local Demo.

Creates all tables in SQLite (stores, skus, inventory, recommendations, feedback_logs, audit_logs).
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


def main():
    print("=" * 60)
    print("📦 AUTOREPLENISH.AI — INISIALISASI DATABASE SQLITE")
    print("=" * 60)

    try:
        db_path = init_db()
        print(f"✅ Database berhasil diinisialisasi pada: {db_path}")

        with get_db_connection(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            ).fetchall()
            table_names = [t["name"] for t in tables]

        print(f"📋 Tabel yang terbentuk ({len(table_names)} tabel):")
        for t in table_names:
            print(f"   • {t}")

        print("\n🚀 Database siap digunakan!")
        print("Langkah selanjutnya: python scripts/02_seed_demo.py")
        print("=" * 60)
    except Exception as e:
        print(f"❌ Terjadi kesalahan saat inisialisasi database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
