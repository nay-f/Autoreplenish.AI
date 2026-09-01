#!/usr/bin/env python3
"""Pre-flight Setup Verification for AutoReplenish.ai Local Demo.

Verifies environment, dependencies, Telegram bot configuration, and network connectivity.
"""

import os
import sys
import socket

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Setup import paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

# Try loading demo/.env or fallback to root .env
env_demo = os.path.join(BASE_DIR, ".env")
env_root = os.path.join(os.path.dirname(BASE_DIR), ".env")
if os.path.exists(env_demo):
    load_dotenv(env_demo)
elif os.path.exists(env_root):
    load_dotenv(env_root)
else:
    load_dotenv()


def main():
    print("=" * 60)
    print("🔍 AUTOREPLENISH.AI — PRE-FLIGHT SYSTEM CHECK")
    print("=" * 60)

    all_passed = True

    # 1. Check Python Version
    py_major = sys.version_info.major
    py_minor = sys.version_info.minor
    if (py_major, py_minor) >= (3, 11):
        print(f"✅ Python Version: {sys.version.split()[0]} (>= 3.11)")
    else:
        print(f"❌ Python Version: {sys.version.split()[0]} (Dibutuhkan Python 3.11+)")
        all_passed = False

    # 2. Check Python Dependencies
    required_packages = ["requests", "dotenv", "fastapi", "uvicorn"]
    missing_packages = []
    for pkg in required_packages:
        try:
            if pkg == "dotenv":
                import dotenv
            elif pkg == "requests":
                import requests
            elif pkg == "fastapi":
                import fastapi
            elif pkg == "uvicorn":
                import uvicorn
        except ImportError:
            missing_packages.append(pkg)

    if not missing_packages:
        print("✅ Python Dependencies: requests, python-dotenv, fastapi, uvicorn terpasang")
    else:
        print(f"❌ Python Dependencies: Paket belum terpasang: {', '.join(missing_packages)}")
        print("   👉 Jalankan: pip install -r requirements.txt")
        all_passed = False

    # 3. Check .env File
    if os.path.exists(env_demo) or os.path.exists(env_root):
        active_env = env_demo if os.path.exists(env_demo) else env_root
        print(f"✅ Konfigurasi .env: Ditemukan ({os.path.basename(active_env)})")
    else:
        print("❌ Konfigurasi .env: File .env tidak ditemukan.")
        print("   👉 Salin .env.example menjadi .env: cp .env.example .env")
        all_passed = False

    # 4. Check Telegram Bot Token
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if token and token not in ["MASUKKAN_TOKEN_BOT_ANDA", "YOUR_BOT_TOKEN_HERE", ""]:
        masked_token = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        print(f"✅ Telegram Bot Token: Terisi ({masked_token})")
    else:
        print("❌ Telegram Bot Token: Belum diisi pada file .env")
        print("   👉 Buka demo/.env dan isi variabel TELEGRAM_BOT_TOKEN dari @BotFather")
        all_passed = False

    # 5. Check Telegram Chat ID
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if chat_id and chat_id not in ["MASUKKAN_CHAT_ID_ANDA", "YOUR_CHAT_ID_HERE", ""]:
        print(f"✅ Telegram Chat ID: Terisi ({chat_id})")
    else:
        print("❌ Telegram Chat ID: Belum diisi pada file .env")
        print("   👉 Buka demo/.env dan isi variabel TELEGRAM_CHAT_ID")
        all_passed = False

    # 6. Check Internet Connection
    try:
        socket.create_connection(("api.telegram.org", 443), timeout=5)
        print("✅ Koneksi Internet: Terhubung ke api.telegram.org (HTTPS)")
    except Exception as e:
        print(f"❌ Koneksi Internet: Gagal terhubung ke api.telegram.org ({e})")
        all_passed = False

    # 7. Check Telegram Bot Validity via API
    bot_info = None
    if token and token not in ["MASUKKAN_TOKEN_BOT_ANDA", "YOUR_BOT_TOKEN_HERE", ""]:
        try:
            from services.telegram_bot import get_bot_info
            bot_info = get_bot_info()
            bot_username = bot_info.get("username", "UnknownBot")
            print(f"✅ Validasi Bot Telegram: Bot aktif (@{bot_username})")
        except Exception as e:
            print(f"❌ Validasi Bot Telegram: Token tidak valid atau bot tidak ditemukan ({e})")
            all_passed = False

    # 8. Check Database Directory Writable
    db_dir = os.path.join(BASE_DIR, "db")
    try:
        os.makedirs(db_dir, exist_ok=True)
        test_file = os.path.join(db_dir, ".test_write")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        print(f"✅ Direktori SQLite DB: Siap & Writable ({db_dir})")
    except Exception as e:
        print(f"❌ Direktori SQLite DB: Gagal menulis ke direktori ({e})")
        all_passed = False

    print("=" * 60)
    if all_passed:
        bot_uname = bot_info.get("username") if bot_info else "BotAnda"
        print("🎉 SEMUA CHECK BERHASIL!")
        print("=" * 60)
        print(f"🤖 Bot: @{bot_uname}")
        print(f"📱 Chat ID: {chat_id}")
        print("🚀 Siap menjalankan demo!")
        print("\nLangkah selanjutnya:")
        print("  1. python scripts/01_init_db.py")
        print("  2. python scripts/02_seed_demo.py")
        print("  3. python scripts/03_run_pipeline.py")
        print("  4. python scripts/04_telegram_listener.py")
        print("  5. python scripts/05_dashboard_api.py")
        print("=" * 60)
        sys.exit(0)
    else:
        print("⚠️ Mohon perbaiki pesan error bertanda ❌ di atas sebelum melanjutkan.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
