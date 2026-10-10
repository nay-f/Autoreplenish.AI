#!/usr/bin/env python3
"""Unified Local Production Runner for AutoReplenish.ai.

Runs:
1. Diagnostic pre-flight check (verifies .env and API connectivity).
2. Telegram Polling Listener (in background thread for offline/local callback handling).
3. FastAPI Backend Server (port 8000).

Usage:
    python run_local_prod.py
    python run_local_prod.py --check-only
"""

import os
import sys
import time
import signal
import threading
import argparse
import subprocess
from typing import Optional, List

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(ROOT_DIR, "demo")
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

for path in [ROOT_DIR, DEMO_DIR, BACKEND_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

from dotenv import load_dotenv

# Load root .env first, then demo/.env as supplementary
env_root = os.path.join(ROOT_DIR, ".env")
env_demo = os.path.join(DEMO_DIR, ".env")
if os.path.exists(env_root):
    load_dotenv(env_root)
if os.path.exists(env_demo):
    load_dotenv(env_demo)


def run_preflight_checks() -> bool:
    """Run diagnostic verification across all production APIs and local database."""
    print("=" * 70)
    print("🚀 AUTOREPLENISH.AI — PRE-FLIGHT SYSTEM DIAGNOSTICS")
    print("=" * 70)

    # 1. Environment files
    env_found = os.path.exists(env_root) or os.path.exists(env_demo)
    if not env_found:
        print("❌ [ENV] Tidak ditemukan berkas .env di root maupun demo/.")
        print("   Silakan salin .env.example menjadi .env dan isi konfigurasi.")
        return False
    print(f"✅ [ENV] Berkas .env terdeteksi.")

    # 2. Database validation
    try:
        from demo.services.local_db import init_db, get_all_stores, get_db_path
        db_path = init_db()
        stores = get_all_stores(active_only=False)
        print(f"✅ [DB] SQLite siap di '{db_path}' ({len(stores)} toko terdaftar).")
        if len(stores) == 0:
            print("   ℹ️ Menjalankan inisialisasi data seed...")
            import importlib
            seeder = importlib.import_module("demo.scripts.02_seed_demo")
            seeder.main()
    except Exception as e:
        print(f"❌ [DB] Error database: {e}")
        return False

    # 3. Telegram Bot API
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if tg_token:
        try:
            import requests
            res = requests.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=5).json()
            if res.get("ok"):
                bot_user = res["result"].get("username", "Unknown")
                print(f"✅ [TELEGRAM] Terhubung ke @{bot_user} (ID: {res['result'].get('id')})")
            else:
                print(f"⚠️ [TELEGRAM] Token tidak valid: {res.get('description')}")
        except Exception as e:
            print(f"⚠️ [TELEGRAM] Gagal verifikasi bot: {e}")
    else:
        print("ℹ️ [TELEGRAM] TELEGRAM_BOT_TOKEN kosong. Mode polling Telegram dinonaktifkan.")

    # 4. OpenWeatherMap API
    weather_key = os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("OPENWEATHER_API_KEY")
    if weather_key:
        try:
            import requests
            w_res = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": -6.2088, "lon": 106.8456, "appid": weather_key, "units": "metric"},
                timeout=5
            )
            if w_res.status_code == 200:
                print(f"✅ [WEATHER] OpenWeatherMap LIVE API terhubung ({w_res.json().get('main', {}).get('temp')}°C)")
            else:
                print(f"⚠️ [WEATHER] OpenWeatherMap merespons HTTP {w_res.status_code}")
        except Exception as e:
            print(f"⚠️ [WEATHER] Gagal menghubungi OpenWeatherMap: {e}")
    else:
        print("ℹ️ [WEATHER] OPENWEATHERMAP_API_KEY kosong. Sistem menggunakan fallback cuaca wilayah.")

    # 5. AWS Bedrock Claude 3.5 Sonnet
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    if aws_key:
        try:
            import boto3
            client = boto3.client("bedrock", region_name=os.getenv("AWS_REGION", "us-east-1"))
            client.list_foundation_models(byProvider="Anthropic")
            print(f"✅ [BEDROCK] AWS Bedrock Claude 3.5 Sonnet terhubung ({os.getenv('AWS_REGION', 'us-east-1')})")
        except Exception as e:
            print(f"⚠️ [BEDROCK] AWS Bedrock belum dapat diakses: {e}")
            print("   Sistem akan menggunakan safe rule-based reasoning engine dengan flag 'is_fallback: True'.")
    else:
        print("ℹ️ [BEDROCK] AWS_ACCESS_KEY_ID kosong. Menggunakan safe rule-based reasoning (is_fallback: True).")

    # 6. SAP S/4HANA & BTP
    sap_client = os.getenv("SAP_CLIENT_ID")
    if sap_client:
        print("✅ [SAP] Kredensial SAP BTP terdeteksi.")
    else:
        print("ℹ️ [SAP] Kredensial SAP kosong. Berjalan dalam mode PERSISTENT SANDBOX (OData {\"d\": {...}} valid).")

    print("=" * 70)
    return True


def start_telegram_listener():
    """Start Telegram long-polling listener in background thread."""
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not tg_token:
        return

    try:
        import importlib
        tg_mod = importlib.import_module("demo.scripts.04_telegram_listener")
        get_updates = getattr(tg_mod, "get_updates")
        handle_approve = getattr(tg_mod, "handle_approve")
        handle_edit_init = getattr(tg_mod, "handle_edit_init")
        handle_reject_init = getattr(tg_mod, "handle_reject_init")
        handle_reg_area = getattr(tg_mod, "handle_reg_area", None)
        handle_reg_ingest = getattr(tg_mod, "handle_reg_ingest", None)
        handle_cmd_callback = getattr(tg_mod, "handle_cmd_callback", None)
        handle_message = getattr(tg_mod, "handle_message", getattr(tg_mod, "handle_text_message"))
        answer_callback_query = getattr(tg_mod, "answer_callback_query")
        tg_logger = getattr(tg_mod, "logger")

        last_update_id = 0
        tg_logger.info("Background Telegram Polling Worker aktif.")

        while True:
            try:
                updates = get_updates(offset=last_update_id + 1, timeout=15)
                for update in updates:
                    last_update_id = update["update_id"]

                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        data = cb.get("data", "")
                        sender_chat_id = str(cb["message"]["chat"]["id"])

                        if ":" in data:
                            action, req_id = data.split(":", 1)
                            if action == "APPROVE":
                                handle_approve(sender_chat_id, req_id, cb_id)
                            elif action == "EDIT":
                                handle_edit_init(sender_chat_id, req_id, cb_id)
                            elif action == "REJECT":
                                handle_reject_init(sender_chat_id, req_id, cb_id)
                            elif action == "REG_AREA" and handle_reg_area:
                                handle_reg_area(sender_chat_id, req_id, cb_id)
                            elif action == "REG_INGEST" and handle_reg_ingest:
                                handle_reg_ingest(sender_chat_id, req_id, cb_id)
                            elif action == "CMD" and handle_cmd_callback:
                                handle_cmd_callback(sender_chat_id, req_id, cb_id)
                            else:
                                answer_callback_query(cb_id, "Aksi tidak dikenal.")

                    elif "message" in update:
                        msg = update["message"]
                        sender_chat_id = str(msg["chat"]["id"])
                        handle_message(sender_chat_id, msg)

                time.sleep(0.5)
            except Exception as e:
                time.sleep(2)

    except Exception as e:
        print(f"⚠️ Telegram worker stopped: {e}")


def spawn_frontend_service(name: str, cwd: str, port: int) -> Optional[subprocess.Popen]:
    """Spawn a Vite frontend service in background subprocess."""
    try:
        cmd = ["npm", "run", "dev", "--", "--port", str(port)]
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            shell=(sys.platform == "win32"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except Exception as e:
        print(f"⚠️ Gagal menjalankan {name}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="AutoReplenish.ai Unified Local Production Runner")
    parser.add_argument("--check-only", action="store_true", help="Hanya jalankan pre-flight checks lalu keluar")
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_API_PORT", 8000)), help="Port backend API (default 8000)")
    parser.add_argument("--dashboard-port", type=int, default=5173, help="Port Web Dashboard Control Center (default 5173)")
    parser.add_argument("--cashier-port", type=int, default=5174, help="Port Web Cashier POS (default 5174)")
    parser.add_argument("--api-only", action="store_true", help="Hanya jalankan backend API tanpa frontend dashboard dan cashier")
    parser.add_argument("--no-dashboard", action="store_true", help="Nonaktifkan Dashboard Control Center")
    parser.add_argument("--no-cashier", action="store_true", help="Nonaktifkan Aplikasi Kasir POS")
    args = parser.parse_args()

    ok = run_preflight_checks()
    if not ok:
        sys.exit(1)

    if args.check_only:
        print("✅ Pemeriksaan pre-flight selesai dengan sukses.")
        sys.exit(0)

    # Spawn Telegram polling listener in a daemon thread
    tg_thread = threading.Thread(target=start_telegram_listener, daemon=True, name="TelegramListener")
    tg_thread.start()

    active_subprocesses: List[subprocess.Popen] = []

    if not args.api_only:
        # 1. Start Dashboard Control Center (React Vite: 5173)
        if not args.no_dashboard:
            dashboard_dir = os.path.join(ROOT_DIR, "dashboard")
            if os.path.exists(dashboard_dir):
                d_proc = spawn_frontend_service("Dashboard Control Center", dashboard_dir, args.dashboard_port)
                if d_proc:
                    active_subprocesses.append(d_proc)
                    print(f"📊 Dashboard Control Center aktif di http://localhost:{args.dashboard_port}")

        # 2. Start Cashier POS Web App (React Vite: 5174)
        if not args.no_cashier:
            cashier_dir = os.path.join(ROOT_DIR, "cashier")
            if os.path.exists(cashier_dir):
                c_proc = spawn_frontend_service("Aplikasi Kasir POS", cashier_dir, args.cashier_port)
                if c_proc:
                    active_subprocesses.append(c_proc)
                    print(f"🛒 Aplikasi Kasir (POS) aktif di http://localhost:{args.cashier_port}")

    # Import and run FastAPI app
    import uvicorn
    import importlib
    api_module = importlib.import_module("demo.scripts.05_dashboard_api")
    app = getattr(api_module, "app")

    print("\n" + "=" * 70)
    print("🚀 3 LAYANAN AUTOREPLENISH.AI BERJALAN:")
    print(f"   1. Backend API:              http://localhost:{args.port} (Docs: /docs)")
    if not args.api_only and not args.no_dashboard:
        print(f"   2. Dashboard Control Center: http://localhost:{args.dashboard_port}")
    if not args.api_only and not args.no_cashier:
        print(f"   3. Aplikasi Kasir (POS):     http://localhost:{args.cashier_port}")
    print("=" * 70)
    print("Tekan Ctrl+C untuk menghentikan seluruh layanan secara bersamaan.\n")

    try:
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
    finally:
        if active_subprocesses:
            print("\n🛑 Mematikan seluruh proses frontend background...")
            for proc in active_subprocesses:
                try:
                    proc.terminate()
                except Exception:
                    pass


if __name__ == "__main__":
    main()

