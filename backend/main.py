import time
import uuid
import logging
import threading
import requests
import boto3
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import backend.src.config as config
from backend.src.auth import (
    verify_password,
    create_access_token,
    get_current_user,
    require_roles,
)
from backend.src.models.schema import (
    StoreProfile,
    SKUItem,
    LoginRequest,
)
from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.services.orchestrator_service import OrchestratorService
from backend.src.services.sap_service import SAPService
from backend.src.services.telegram_service import TelegramService

# Konfigurasi Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("autoreplenish.api")

app = FastAPI(title="AutoReplenish.ai Production API", version="1.1.0")

# P0 #4: Batasi CORS hanya ke origin dashboard yang diizinkan
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

db = DynamoDBService()
orchestrator = OrchestratorService()
sap_svc = SAPService(db)
tg_svc = TelegramService(db)

def handle_telegram_update(update: dict):
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        data = cb.get("data", "")
        chat_id = str(cb["message"]["chat"]["id"])
        message_id = cb["message"]["message_id"]

        # 1. Pilihan Area pada Registrasi Toko (Disimpan di DynamoDB)
        if data.startswith("REG_AREA:"):
            area_choice = data.split(":", 1)[1]
            session = db.get_telegram_session(chat_id)
            if session:
                session["area_type"] = area_choice
                session["step"] = "WAIT_LOCATION"
                db.save_telegram_session(chat_id, session)
                tg_svc.answer_callback(cb_id, f"Tipe area: {area_choice}")
                _send_tg_text(
                    chat_id,
                    "📍 *Langkah 3/4: Koordinat GPS Toko*\n"
                    "Silakan kirim lokasi toko Anda menggunakan fitur *Attach (📎) -> Location (Lokasi)* di Telegram, "
                    "atau ketik koordinat manual dengan format: `-6.9666, 110.4166`",
                )
            else:
                tg_svc.answer_callback(cb_id, "Sesi pendaftaran telah kedaluwarsa. Ketik /tambah_toko lagi.")
            return

        # 2. Pemicu Analisa On-Demand via Tombol Telegram
        if data.startswith("RUN_EVAL:"):
            target_store_id = data.split(":", 1)[1]
            tg_svc.answer_callback(cb_id, "Memulai analisa...")
            _send_tg_text(
                chat_id,
                f"⏳ Sedang menjalankan analisa kognitif untuk toko *{target_store_id}*...",
            )
            res = orchestrator.evaluate_store(target_store_id, force_all=True)
            if res.get("skipped_locked"):
                _send_tg_text(chat_id, f"⚠️ {res.get('message')}")
            else:
                _send_tg_text(
                    chat_id,
                    f"✅ Analisa selesai untuk *{res['store_name']}*.\n"
                    f"Cuaca saat ini: {res['weather'].get('condition')} ({res['weather'].get('temperature_c')}°C).\n"
                    f"Total SKU dievaluasi: {res['evaluated_count']} item.",
                )
            return

        # 3. Eksekusi Tombol APPROVE / EDIT / REJECT dengan Atomic Conditional Lock
        if ":" in data:
            action, req_id = data.split(":", 1)
            state = db.get_approval_state(req_id)
            if not state:
                tg_svc.answer_callback(cb_id, "Data request tidak ditemukan.")
                return

            if action == "APPROVE":
                # Atomic Lock: Ubah PENDING_APPROVAL -> SAP_SUBMITTING
                locked = db.transition_approval_state(
                    request_id=req_id,
                    expected_current_statuses=["PENDING_APPROVAL", "EDIT_REQUESTED"],
                    new_status="SAP_SUBMITTING",
                )
                if not locked:
                    tg_svc.answer_callback(
                        cb_id, f"Pesanan ini sudah diproses ({state.status})."
                    )
                    return

                tg_svc.answer_callback(cb_id, "Menyetujui & memproses PR SAP...")
                store_obj, sku_obj = _resolve_store_and_sku(
                    state.store_id, state.sku_id, state.sku_name
                )
                pr = sap_svc.create_purchase_requisition(
                    store=store_obj,
                    sku=sku_obj,
                    quantity=state.recommended_qty,
                    idempotency_key=req_id,
                )
                final_status = (
                    "SAP_SUBMITTED"
                    if pr["status"] in ("SAP_SUBMITTED", "BTP_VERIFIED_SANDBOX_PR")
                    else "SAP_FAILED"
                )
                db.transition_approval_state(
                    request_id=req_id,
                    expected_current_statuses=["SAP_SUBMITTING"],
                    new_status=final_status,
                    final_qty=state.recommended_qty,
                    sap_pr_id=pr["pr_number"],
                )
                tg_svc.update_message_status(
                    chat_id,
                    message_id,
                    f"✅ *PESANAN DISETUJUI*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ *SKU:* {sku_obj.sku_name}\n"
                    f"📦 *Kuota Disetujui:* `{state.recommended_qty} Pcs`\n"
                    f"💰 *Estimasi Nilai:* `Rp {pr['total_amount']:,.0f}`\n"
                    f"📄 *No. PR SAP:* `{pr['pr_number']}`\n"
                    f"📡 *Status SAP:* `{pr['status']}`",
                )

            elif action == "REJECT":
                locked = db.transition_approval_state(
                    request_id=req_id,
                    expected_current_statuses=["PENDING_APPROVAL", "EDIT_REQUESTED"],
                    new_status="REJECTED",
                    final_qty=0,
                    rejection_reason="Ditolak oleh Kepala Toko",
                )
                if not locked:
                    tg_svc.answer_callback(
                        cb_id, f"Pesanan ini sudah diproses ({state.status})."
                    )
                    return

                tg_svc.answer_callback(cb_id, "Pesanan ditolak.")
                tg_svc.update_message_status(
                    chat_id,
                    message_id,
                    f"❌ *PESANAN DITOLAK*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ *SKU:* {state.sku_name or state.sku_id}\n"
                    f"Tidak ada Purchase Requisition yang diterbitkan.",
                )

            elif action == "EDIT":
                locked = db.transition_approval_state(
                    request_id=req_id,
                    expected_current_statuses=["PENDING_APPROVAL", "EDIT_REQUESTED"],
                    new_status="EDIT_REQUESTED",
                )
                if not locked:
                    tg_svc.answer_callback(
                        cb_id, f"Pesanan ini sudah diproses ({state.status})."
                    )
                    return

                tg_svc.answer_callback(cb_id, "Silakan ketik jumlah unit baru")
                db.save_telegram_session(
                    chat_id,
                    {
                        "step": "WAIT_EDIT_QTY",
                        "req_id": req_id,
                        "message_id": message_id,
                    },
                )
                _send_tg_text(
                    chat_id,
                    f"✏️ Ketik jumlah unit pesanan baru untuk *{state.sku_name or state.sku_id}* (angka saja, misal: `36`):",
                )
        return

    if "message" in update:
        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").strip()
        location = msg.get("location")

        if text in ["/start", "/help"]:
            _send_tg_text(
                chat_id,
                "🤖 *Selamat Datang di AutoReplenish.ai Bot*\n\n"
                "Perintah yang tersedia:\n"
                "• `/tambah_toko` — Daftarkan toko baru & atur titik GPS\n"
                "• `/analisa` — Jalankan analisa stok instan (on-demand)\n"
                "• `/daftar_toko` — Lihat daftar toko yang aktif",
            )
            return

        if text == "/daftar_toko":
            stores = db.list_stores()
            if not stores:
                _send_tg_text(chat_id, "Belum ada toko terdaftar.")
                return
            lines = ["🏪 *Daftar Toko Aktif:*"]
            for s in stores:
                lines.append(f"• `{s.store_id}` — *{s.store_name}* ({s.area_type})")
            _send_tg_text(chat_id, "\n".join(lines))
            return

        if text.startswith("/analisa"):
            stores = db.list_stores()
            if not stores:
                _send_tg_text(
                    chat_id,
                    "Belum ada toko terdaftar. Gunakan `/tambah_toko` terlebih dahulu.",
                )
                return
            buttons = [
                [
                    {
                        "text": f"⚡ {s.store_name} ({s.store_id})",
                        "callback_data": f"RUN_EVAL:{s.store_id}",
                    }
                ]
                for s in stores
            ]
            _send_tg_text(
                chat_id,
                "Pilih toko yang ingin dianalisa sekarang (tidak mengganggu jadwal otomatis 3 jam):",
                reply_markup={"inline_keyboard": buttons},
            )
            return

        if text in ["/tambah_toko", "/register_store"]:
            db.save_telegram_session(chat_id, {"step": "WAIT_STORE_NAME"})
            _send_tg_text(
                chat_id,
                "🏪 *Langkah 1/4: Nama Toko*\nSilakan ketik nama toko baru Anda (contoh: `Toko Almadina Wirosari`):",
            )
            return

        # Baca state sesi percakapan dari DynamoDB
        session = db.get_telegram_session(chat_id)
        if not session:
            return

        step = session.get("step")

        if step == "WAIT_STORE_NAME" and text:
            clean_slug = "".join(c for c in text.upper() if c.isalnum())[:6]
            session["store_name"] = text
            session["store_id"] = f"STR-{clean_slug}-{uuid.uuid4().hex[:2].upper()}"
            session["step"] = "WAIT_AREA"
            db.save_telegram_session(chat_id, session)
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🏢 Komersial / Perkantoran",
                            "callback_data": "REG_AREA:Komersial / Perkantoran",
                        }
                    ],
                    [
                        {
                            "text": "🏡 Residensial / Pemukiman",
                            "callback_data": "REG_AREA:Residensial / Pemukiman",
                        }
                    ],
                    [
                        {
                            "text": "🌾 Pasar / Sub-Urban",
                            "callback_data": "REG_AREA:Pasar / Sub-Urban",
                        }
                    ],
                ]
            }
            _send_tg_text(
                chat_id,
                f"ID Toko dibuat: `{session['store_id']}`\n\n"
                "🏙️ *Langkah 2/4: Pilih Tipe Wilayah Toko:*",
                reply_markup=keyboard,
            )
            return

        if step == "WAIT_LOCATION":
            if location:
                session["latitude"] = float(location["latitude"])
                session["longitude"] = float(location["longitude"])
            elif "," in text:
                try:
                    lat_s, lon_s = text.split(",", 1)
                    lat_v, lon_v = float(lat_s.strip()), float(lon_s.strip())
                    if not (-90 <= lat_v <= 90 and -180 <= lon_v <= 180):
                        raise ValueError("Rentang koordinat di luar batas bumi.")
                    session["latitude"] = lat_v
                    session["longitude"] = lon_v
                except ValueError:
                    _send_tg_text(
                        chat_id,
                        "Format koordinat tidak valid (Lat -90 s/d 90, Lon -180 s/d 180). Contoh: `-7.0864, 111.1687`",
                    )
                    return
            else:
                _send_tg_text(
                    chat_id, "Silakan bagikan lokasi GPS atau ketik `lat, lon`."
                )
                return

            session["step"] = "WAIT_ZONE"
            db.save_telegram_session(chat_id, session)
            _send_tg_text(
                chat_id,
                f"✅ Koordinat terekam: `{session['latitude']}, {session['longitude']}`\n\n"
                "🚚 *Langkah 4/4: Kode Zona Logistik DC*\n"
                "Ketik kode zona pengiriman (contoh: `ZONE-GROBOGAN-01` atau `ZONE-SMG-01`):",
            )
            return

        if step == "WAIT_ZONE" and text:
            new_store = StoreProfile(
                store_id=session["store_id"],
                store_name=session["store_name"],
                area_type=session["area_type"],
                zone=text.upper()[:64],
                latitude=session["latitude"],
                longitude=session["longitude"],
                telegram_chat_id=chat_id,
                ingestion_mode="POS_LOCAL",
            )
            db.save_store(new_store)
            default_sku = SKUItem(
                sku_id="SKU-MINYAK-01",
                sku_name="Minyak Goreng Pouch 2L",
                category="Daily Staples",
                physical_stock=8,
                threshold=20,
                average_daily_burn_rate=12.0,
                lead_time_days=2,
                moq=12,
                packaging_multiple=12,
                unit_price=34500.0,
                is_perishable=False,
            )
            db.save_sku(new_store.store_id, default_sku)
            db.delete_telegram_session(chat_id)

            _send_tg_text(
                chat_id,
                f"🎉 *Toko Berhasil Terdaftar & Sinkron ke Dashboard!*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 *ID:* `{new_store.store_id}`\n"
                f"🏪 *Nama:* {new_store.store_name}\n"
                f"🏙️ *Wilayah:* {new_store.area_type}\n"
                f"📍 *GPS:* `{new_store.latitude}, {new_store.longitude}`\n"
                f"🚚 *Zona:* `{new_store.zone}`\n\n"
                f"Ketik `/analisa` untuk menguji evaluasi AI pada toko ini sekarang.",
            )
            return

        if step == "WAIT_EDIT_QTY" and text:
            try:
                new_qty = int(text)
                if new_qty <= 0 or new_qty > 100000:
                    raise ValueError("Kuota harus antara 1 - 100.000")
                req_id = session["req_id"]
                state = db.get_approval_state(req_id)

                locked = db.transition_approval_state(
                    request_id=req_id,
                    expected_current_statuses=["EDIT_REQUESTED", "PENDING_APPROVAL"],
                    new_status="SAP_SUBMITTING",
                )
                if state and locked:
                    store_obj, sku_obj = _resolve_store_and_sku(
                        state.store_id, state.sku_id, state.sku_name
                    )
                    pr = sap_svc.create_purchase_requisition(
                        store=store_obj,
                        sku=sku_obj,
                        quantity=new_qty,
                        idempotency_key=req_id,
                    )
                    db.transition_approval_state(
                        request_id=req_id,
                        expected_current_statuses=["SAP_SUBMITTING"],
                        new_status="EDITED",
                        final_qty=new_qty,
                        sap_pr_id=pr["pr_number"],
                    )
                    _send_tg_text(
                        chat_id,
                        f"✅ *KUOTA DIREVISI & DISETUJUI*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏷️ *SKU:* {sku_obj.sku_name}\n"
                        f"📦 *Kuota Baru:* `{new_qty} Pcs` (Rekomendasi awal: {state.recommended_qty})\n"
                        f"💰 *Total Nilai:* `Rp {pr['total_amount']:,.0f}`\n"
                        f"📄 *No. PR SAP:* `{pr['pr_number']}`\n"
                        f"📡 *Status SAP:* `{pr['status']}`",
                    )
                else:
                    _send_tg_text(chat_id, "⚠️ Request ini sudah tidak dapat diubah.")
                db.delete_telegram_session(chat_id)
            except ValueError:
                _send_tg_text(
                    chat_id, "Masukkan angka bulat positif yang valid (1 - 100000)."
                )


# P0 #6: Global Exception Handler agar tidak membocorkan stack trace internal ke client
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = uuid.uuid4().hex[:10]
    logger.error(
        "Unhandled exception [correlation_id=%s] pada %s: %s",
        correlation_id,
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Terjadi kesalahan internal pada server. Silakan hubungi administrator.",
            "correlation_id": correlation_id,
        },
    )


# Helper: Ambil objek Store & SKU untuk penerbitan PR SAP yang akurat
def _resolve_store_and_sku(store_id: str, sku_id: str, fallback_sku_name: str = ""):
    store = db.get_store(store_id) or StoreProfile(
        store_id=store_id, store_name=store_id
    )
    skus = db.get_skus_for_store(store_id)
    sku = next((s for s in skus if s.sku_id == sku_id), None)
    if not sku:
        sku = SKUItem(
            sku_id=sku_id,
            sku_name=fallback_sku_name or sku_id,
            physical_stock=0,
            threshold=10,
            average_daily_burn_rate=5.0,
            unit_price=15000.0,
        )
    return store, sku


# =====================================================================
# 1. ENDPOINT AUTENTIKASI JWT & HEALTHCHECK
# =====================================================================

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    if req.username == config.ADMIN_USERNAME and verify_password(
        req.password, config.ADMIN_PASSWORD_HASH
    ):
        jwt_token = create_access_token(username=req.username, role=req.role)
        logger.info("User '%s' berhasil login dengan peran '%s'", req.username, req.role)
        return {
            "authenticated": True,
            "token": jwt_token,
            "user": {
                "username": req.username,
                "role": req.role,
            },
        }
    logger.warning("Percobaan login gagal untuk username '%s'", req.username)
    raise HTTPException(status_code=401, detail="Username atau password tidak sesuai.")


@app.get("/api/v1/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/api/v1/health/integrations")
def check_integrations_health(current_user: dict = Depends(get_current_user)):
    """Memeriksa status riil seluruh API eksternal tanpa membocorkan token/secret."""
    status_report = {}

    # 1. Cek AWS Bedrock
    if not config.AWS_ACCESS_KEY_ID or not config.BEDROCK_MODEL_ID:
        status_report["bedrock"] = {
            "status": "NOT_CONFIGURED",
            "detail": "Kredensial AWS / Model ID kosong",
        }
    else:
        try:
            bedrock_ctrl = boto3.client(
                "bedrock",
                region_name=config.AWS_REGION,
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            )
            bedrock_ctrl.list_foundation_models(byProvider="Anthropic")
            status_report["bedrock"] = {
                "status": "CONNECTED",
                "model": config.BEDROCK_MODEL_ID,
            }
        except Exception:
            status_report["bedrock"] = {
                "status": "ERROR",
                "detail": "Gagal terhubung ke AWS Bedrock",
            }

    # 2. Cek OpenWeatherMap API
    if not config.OPENWEATHER_API_KEY:
        status_report["weather"] = {
            "status": "NOT_CONFIGURED",
            "detail": "OPENWEATHER_API_KEY kosong",
        }
    else:
        try:
            r = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": -6.9666,
                    "lon": 110.4166,
                    "appid": config.OPENWEATHER_API_KEY,
                },
                timeout=5,
            )
            if r.status_code == 200:
                status_report["weather"] = {
                    "status": "CONNECTED",
                    "detail": "OpenWeatherMap Aktif",
                }
            else:
                status_report["weather"] = {
                    "status": "ERROR",
                    "detail": f"HTTP {r.status_code}",
                }
        except Exception:
            status_report["weather"] = {
                "status": "ERROR",
                "detail": "Gagal menghubungi OpenWeatherMap",
            }

    # 3. Cek Telegram Bot API
    status_report["telegram"] = tg_svc.verify_bot()

    # 4. Cek SAP BTP OAuth2 (Tanpa token_prefix)
    if not config.SAP_TOKEN_URL or not config.SAP_CLIENT_ID or not config.SAP_CLIENT_SECRET:
        status_report["sap"] = {
            "status": "NOT_CONFIGURED",
            "detail": "Kredensial SAP BTP belum diisi",
        }
    else:
        status_report["sap"] = sap_svc.verify_connection()

    return status_report


# =====================================================================
# 2. ENDPOINT MANAJEMEN TOKO & SKU (DIPROTEKSI JWT + RBAC)
# =====================================================================

@app.get("/api/v1/stores")
def list_all_stores(current_user: dict = Depends(get_current_user)):
    return db.list_stores()


@app.get("/api/v1/stores/{store_id}")
def get_store_detail(store_id: str, current_user: dict = Depends(get_current_user)):
    store = db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Toko tidak ditemukan")
    skus = db.get_skus_for_store(store_id)
    return {"store": store, "skus": skus}


@app.post("/api/v1/stores")
def create_or_update_store(
    store: StoreProfile,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator"])
    ),
):
    return db.save_store(store)


@app.put("/api/v1/stores/{store_id}")
def update_store_settings(
    store_id: str,
    store: StoreProfile,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator"])
    ),
):
    store.store_id = store_id
    return db.save_store(store)


@app.get("/api/v1/stores/{store_id}/skus")
def get_store_skus(store_id: str, current_user: dict = Depends(get_current_user)):
    return db.get_skus_for_store(store_id)


@app.post("/api/v1/stores/{store_id}/skus")
def save_store_sku(
    store_id: str,
    sku: SKUItem,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator"])
    ),
):
    return db.save_sku(store_id, sku)


@app.delete("/api/v1/stores/{store_id}/skus/{sku_id}")
def remove_store_sku(
    store_id: str,
    sku_id: str,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator"])
    ),
):
    db.delete_sku(store_id, sku_id)
    return {"deleted": True, "sku_id": sku_id}


# =====================================================================
# 3. ENDPOINT EVALUASI ON-DEMAND & AUDIT LOGS
# =====================================================================

@app.post("/api/v1/evaluate/{store_id}")
def trigger_store_evaluation(
    store_id: str,
    force_all: bool = True,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator"])
    ),
):
    try:
        return orchestrator.evaluate_store(store_id, force_all=force_all)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/audit-logs")
def fetch_audit_logs(
    store_id: str = None,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator", "Auditor"])
    ),
):
    return db.get_audit_logs(store_id)

@app.get("/api/v1/metrics/governance")
def get_governance_and_accuracy_metrics(
    store_id: str = None,
    current_user: dict = Depends(
        require_roles(["Store Manager", "Regional Manager", "IT Administrator", "Auditor"])
    ),
):
    """
    Menghitung metrik observability & akurasi AI secara aktual dari rekam jejak DynamoDB
    tanpa angka hardcoded (P0 #7 & P1 #20).
    """
    logs = db.get_audit_logs(store_id)
    eval_logs = [item for item in logs if "sap_pr" not in item]
    pr_logs = [item["sap_pr"] for item in logs if "sap_pr" in item]

    total_evals = len(eval_logs)
    fallback_count = sum(1 for item in eval_logs if item.get("is_fallback"))
    guardrail_count = sum(1 for item in eval_logs if item.get("guardrail_applied"))

    latencies = [item.get("latency_ms", 0) for item in eval_logs if item.get("latency_ms")]
    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0

    # Hitung status persetujuan aktual dari tabel REQ#<id>
    approved_count = 0
    edited_count = 0
    rejected_count = 0
    pending_count = 0
    abs_qty_diff_sum = 0
    actual_qty_sum = 0

    for item in eval_logs[:50]:
        req_id = item.get("request_id")
        if not req_id:
            continue
        st = db.get_approval_state(req_id)
        if not st:
            continue
        if st.status in ("APPROVED", "SAP_SUBMITTED"):
            approved_count += 1
            final_q = st.final_qty if st.final_qty is not None else st.recommended_qty
            abs_qty_diff_sum += abs(final_q - st.recommended_qty)
            actual_qty_sum += final_q
        elif st.status == "EDITED":
            edited_count += 1
            final_q = st.final_qty if st.final_qty is not None else st.recommended_qty
            abs_qty_diff_sum += abs(final_q - st.recommended_qty)
            actual_qty_sum += final_q
        elif st.status == "REJECTED":
            rejected_count += 1
        else:
            pending_count += 1

    decided_total = approved_count + edited_count + rejected_count
    acceptance_rate = round((approved_count / decided_total) * 100, 1) if decided_total else 0.0
    edit_rate = round((edited_count / decided_total) * 100, 1) if decided_total else 0.0
    rejection_rate = round((rejected_count / decided_total) * 100, 1) if decided_total else 0.0

    # WAPE (Weighted Absolute Percentage Error) terhadap keputusan final Kepala Toko
    wape_percent = round((abs_qty_diff_sum / actual_qty_sum) * 100, 1) if actual_qty_sum > 0 else 0.0
    ai_alignment_accuracy = round(max(0.0, 100.0 - wape_percent), 1) if actual_qty_sum > 0 else None

    # Metrik Transaksi SAP PR
    total_prs = len(pr_logs)
    sap_success = sum(
        1 for p in pr_logs if p.get("status") in ("SAP_SUBMITTED", "BTP_VERIFIED_SANDBOX_PR")
    )
    sap_failed = total_prs - sap_success

    return {
        "version_info": {
            "model_id": config.BEDROCK_MODEL_ID,
            "prompt_version": config.PROMPT_VERSION,
            "rule_engine_version": config.RULE_ENGINE_VERSION,
        },
        "evaluation_metrics": {
            "total_evaluations": total_evals,
            "bedrock_fallback_total": fallback_count,
            "bedrock_fallback_rate_pct": round((fallback_count / total_evals) * 100, 1) if total_evals else 0.0,
            "guardrail_interventions_total": guardrail_count,
            "average_bedrock_latency_ms": avg_latency_ms,
        },
        "hitl_decision_metrics": {
            "decided_total": decided_total,
            "pending_total": pending_count,
            "approved_unchanged_total": approved_count,
            "edited_by_manager_total": edited_count,
            "rejected_total": rejected_count,
            "acceptance_rate_pct": acceptance_rate,
            "edit_rate_pct": edit_rate,
            "rejection_rate_pct": rejection_rate,
            "manager_alignment_wape_pct": wape_percent,
            "manager_alignment_accuracy_pct": ai_alignment_accuracy,
        },
        "sap_transaction_metrics": {
            "sap_pr_total": total_prs,
            "sap_pr_success_total": sap_success,
            "sap_pr_failure_total": sap_failed,
            "sap_success_rate_pct": round((sap_success / total_prs) * 100, 1) if total_prs else 0.0,
        },
    }
# =====================================================================
# 4. BACKGROUND TELEGRAM POLLER (DENGAN PROTEKSI DUPLIKASI APPROVAL)
# =====================================================================

def _send_tg_text(chat_id: str, text: str, reply_markup: dict = None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{tg_svc.base_url}/sendMessage", json=payload, timeout=5)


def handle_telegram_update(update: dict):
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        data = cb.get("data", "")
        chat_id = str(cb["message"]["chat"]["id"])
        message_id = cb["message"]["message_id"]

        if data.startswith("REG_AREA:"):
            area_choice = data.split(":", 1)[1]
            if chat_id in TELEGRAM_SESSIONS:
                TELEGRAM_SESSIONS[chat_id]["area_type"] = area_choice
                TELEGRAM_SESSIONS[chat_id]["step"] = "WAIT_LOCATION"
                tg_svc.answer_callback(cb_id, f"Tipe area: {area_choice}")
                _send_tg_text(
                    chat_id,
                    "📍 *Langkah 3/4: Koordinat GPS Toko*\n"
                    "Silakan kirim lokasi toko Anda menggunakan fitur *Attach (📎) -> Location (Lokasi)* di Telegram, "
                    "atau ketik koordinat manual dengan format: `-6.9666, 110.4166`",
                )
            return

        if data.startswith("RUN_EVAL:"):
            target_store_id = data.split(":", 1)[1]
            tg_svc.answer_callback(cb_id, "Memulai analisa...")
            _send_tg_text(
                chat_id,
                f"⏳ Sedang menjalankan analisa kognitif untuk toko *{target_store_id}*...",
            )
            res = orchestrator.evaluate_store(target_store_id, force_all=True)
            _send_tg_text(
                chat_id,
                f"✅ Analisa selesai untuk *{res['store_name']}*.\n"
                f"Cuaca saat ini: {res['weather'].get('condition')} ({res['weather'].get('temperature_c')}°C).\n"
                f"Total SKU dievaluasi: {res['evaluated_count']} item.",
            )
            return

        if ":" in data:
            action, req_id = data.split(":", 1)
            state = db.get_approval_state(req_id)
            if not state:
                tg_svc.answer_callback(cb_id, "Data request tidak ditemukan.")
                return

            # P0 #8: Cegah duplikasi klik apabila request sudah pernah diproses
            if state.status != "PENDING_APPROVAL":
                tg_svc.answer_callback(
                    cb_id, f"Request ini sudah berstatus {state.status}."
                )
                return

            if action == "APPROVE":
                tg_svc.answer_callback(cb_id, "Menyetujui & memproses PR SAP...")
                store_obj, sku_obj = _resolve_store_and_sku(
                    state.store_id, state.sku_id, state.sku_name
                )
                pr = sap_svc.create_purchase_requisition(
                    store=store_obj,
                    sku=sku_obj,
                    quantity=state.recommended_qty,
                    idempotency_key=req_id,
                )
                final_status = (
                    "SAP_SUBMITTED"
                    if pr["status"] in ("SAP_SUBMITTED", "BTP_VERIFIED_SANDBOX_PR")
                    else "SAP_FAILED"
                )
                db.update_approval_state(
                    req_id,
                    final_status,
                    final_qty=state.recommended_qty,
                    sap_pr_id=pr["pr_number"],
                )
                tg_svc.update_message_status(
                    chat_id,
                    message_id,
                    f"✅ *PESANAN DISETUJUI*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ *SKU:* {sku_obj.sku_name}\n"
                    f"📦 *Kuota Disetujui:* `{state.recommended_qty} Pcs`\n"
                    f"💰 *Estimasi Nilai:* `Rp {pr['total_amount']:,.0f}`\n"
                    f"📄 *No. PR SAP:* `{pr['pr_number']}`\n"
                    f"📡 *Status SAP:* `{pr['status']}`",
                )

            elif action == "REJECT":
                tg_svc.answer_callback(cb_id, "Pesanan ditolak.")
                db.update_approval_state(
                    req_id,
                    "REJECTED",
                    final_qty=0,
                    rejection_reason="Ditolak oleh Kepala Toko",
                )
                tg_svc.update_message_status(
                    chat_id,
                    message_id,
                    f"❌ *PESANAN DITOLAK*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ *SKU:* {state.sku_name or state.sku_id}\n"
                    f"Tidak ada Purchase Requisition yang diterbitkan.",
                )

            elif action == "EDIT":
                tg_svc.answer_callback(cb_id, "Silakan ketik jumlah unit baru")
                TELEGRAM_SESSIONS[chat_id] = {
                    "step": "WAIT_EDIT_QTY",
                    "req_id": req_id,
                    "message_id": message_id,
                }
                _send_tg_text(
                    chat_id,
                    f"✏️ Ketik jumlah unit pesanan baru untuk *{state.sku_name or state.sku_id}* (angka saja, misal: `36`):",
                )
        return

    if "message" in update:
        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").strip()
        location = msg.get("location")

        if text in ["/start", "/help"]:
            _send_tg_text(
                chat_id,
                "🤖 *Selamat Datang di AutoReplenish.ai Bot*\n\n"
                "Perintah yang tersedia:\n"
                "• `/tambah_toko` — Daftarkan toko baru & atur titik GPS\n"
                "• `/analisa` — Jalankan analisa stok instan (on-demand)\n"
                "• `/daftar_toko` — Lihat daftar toko yang aktif",
            )
            return

        if text == "/daftar_toko":
            stores = db.list_stores()
            if not stores:
                _send_tg_text(chat_id, "Belum ada toko terdaftar.")
                return
            lines = ["🏪 *Daftar Toko Aktif:*"]
            for s in stores:
                lines.append(f"• `{s.store_id}` — *{s.store_name}* ({s.area_type})")
            _send_tg_text(chat_id, "\n".join(lines))
            return

        if text.startswith("/analisa"):
            stores = db.list_stores()
            if not stores:
                _send_tg_text(
                    chat_id,
                    "Belum ada toko terdaftar. Gunakan `/tambah_toko` terlebih dahulu.",
                )
                return
            buttons = [
                [
                    {
                        "text": f"⚡ {s.store_name} ({s.store_id})",
                        "callback_data": f"RUN_EVAL:{s.store_id}",
                    }
                ]
                for s in stores
            ]
            _send_tg_text(
                chat_id,
                "Pilih toko yang ingin dianalisa sekarang (tidak mengganggu jadwal otomatis 3 jam):",
                reply_markup={"inline_keyboard": buttons},
            )
            return

        if text in ["/tambah_toko", "/register_store"]:
            TELEGRAM_SESSIONS[chat_id] = {"step": "WAIT_STORE_NAME"}
            _send_tg_text(
                chat_id,
                "🏪 *Langkah 1/4: Nama Toko*\nSilakan ketik nama toko baru Anda (contoh: `Toko Almadina Wirosari`):",
            )
            return

        session = TELEGRAM_SESSIONS.get(chat_id)
        if not session:
            return

        step = session.get("step")

        if step == "WAIT_STORE_NAME" and text:
            clean_slug = "".join(c for c in text.upper() if c.isalnum())[:6]
            session["store_name"] = text
            session["store_id"] = f"STR-{clean_slug}-{uuid.uuid4().hex[:2].upper()}"
            session["step"] = "WAIT_AREA"
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🏢 Komersial / Perkantoran",
                            "callback_data": "REG_AREA:Komersial / Perkantoran",
                        }
                    ],
                    [
                        {
                            "text": "🏡 Residensial / Pemukiman",
                            "callback_data": "REG_AREA:Residensial / Pemukiman",
                        }
                    ],
                    [
                        {
                            "text": "🌾 Pasar / Sub-Urban",
                            "callback_data": "REG_AREA:Pasar / Sub-Urban",
                        }
                    ],
                ]
            }
            _send_tg_text(
                chat_id,
                f"ID Toko dibuat: `{session['store_id']}`\n\n"
                "🏙️ *Langkah 2/4: Pilih Tipe Wilayah Toko:*",
                reply_markup=keyboard,
            )
            return

        if step == "WAIT_LOCATION":
            if location:
                session["latitude"] = float(location["latitude"])
                session["longitude"] = float(location["longitude"])
            elif "," in text:
                try:
                    lat_s, lon_s = text.split(",", 1)
                    lat_v, lon_v = float(lat_s.strip()), float(lon_s.strip())
                    if not (-90 <= lat_v <= 90 and -180 <= lon_v <= 180):
                        raise ValueError("Rentang koordinat di luar batas bumi.")
                    session["latitude"] = lat_v
                    session["longitude"] = lon_v
                except ValueError:
                    _send_tg_text(
                        chat_id,
                        "Format koordinat tidak valid (Lat -90 s/d 90, Lon -180 s/d 180). Contoh: `-7.0864, 111.1687`",
                    )
                    return
            else:
                _send_tg_text(
                    chat_id, "Silakan bagikan lokasi GPS atau ketik `lat, lon`."
                )
                return

            session["step"] = "WAIT_ZONE"
            _send_tg_text(
                chat_id,
                f"✅ Koordinat terekam: `{session['latitude']}, {session['longitude']}`\n\n"
                "🚚 *Langkah 4/4: Kode Zona Logistik DC*\n"
                "Ketik kode zona pengiriman (contoh: `ZONE-GROBOGAN-01` atau `ZONE-SMG-01`):",
            )
            return

        if step == "WAIT_ZONE" and text:
            new_store = StoreProfile(
                store_id=session["store_id"],
                store_name=session["store_name"],
                area_type=session["area_type"],
                zone=text.upper()[:64],
                latitude=session["latitude"],
                longitude=session["longitude"],
                telegram_chat_id=chat_id,
                ingestion_mode="POS_LOCAL",
            )
            db.save_store(new_store)
            default_sku = SKUItem(
                sku_id="SKU-MINYAK-01",
                sku_name="Minyak Goreng Pouch 2L",
                category="Daily Staples",
                physical_stock=8,
                threshold=20,
                average_daily_burn_rate=12.0,
                lead_time_days=2,
                moq=12,
                packaging_multiple=12,
                unit_price=34500.0,
                is_perishable=False,
            )
            db.save_sku(new_store.store_id, default_sku)
            del TELEGRAM_SESSIONS[chat_id]

            _send_tg_text(
                chat_id,
                f"🎉 *Toko Berhasil Terdaftar & Sinkron ke Dashboard!*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 *ID:* `{new_store.store_id}`\n"
                f"🏪 *Nama:* {new_store.store_name}\n"
                f"🏙️ *Wilayah:* {new_store.area_type}\n"
                f"📍 *GPS:* `{new_store.latitude}, {new_store.longitude}`\n"
                f"🚚 *Zona:* `{new_store.zone}`\n\n"
                f"Ketik `/analisa` untuk menguji evaluasi AI pada toko ini sekarang.",
            )
            return

        if step == "WAIT_EDIT_QTY" and text:
            try:
                new_qty = int(text)
                if new_qty <= 0 or new_qty > 100000:
                    raise ValueError("Kuota harus antara 1 - 100.000")
                req_id = session["req_id"]
                state = db.get_approval_state(req_id)
                if state and state.status == "PENDING_APPROVAL":
                    store_obj, sku_obj = _resolve_store_and_sku(
                        state.store_id, state.sku_id, state.sku_name
                    )
                    pr = sap_svc.create_purchase_requisition(
                        store=store_obj,
                        sku=sku_obj,
                        quantity=new_qty,
                        idempotency_key=req_id,
                    )
                    db.update_approval_state(
                        req_id, "EDITED", final_qty=new_qty, sap_pr_id=pr["pr_number"]
                    )
                    _send_tg_text(
                        chat_id,
                        f"✅ *KUOTA DIREVISI & DISETUJUI*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏷️ *SKU:* {sku_obj.sku_name}\n"
                        f"📦 *Kuota Baru:* `{new_qty} Pcs` (Rekomendasi awal: {state.recommended_qty})\n"
                        f"💰 *Total Nilai:* `Rp {pr['total_amount']:,.0f}`\n"
                        f"📄 *No. PR SAP:* `{pr['pr_number']}`\n"
                        f"📡 *Status SAP:* `{pr['status']}`",
                    )
                del TELEGRAM_SESSIONS[chat_id]
            except ValueError:
                _send_tg_text(
                    chat_id, "Masukkan angka bulat positif yang valid (1 - 100000)."
                )


def telegram_polling_worker():
    if not config.TELEGRAM_BOT_TOKEN:
        return
    offset = 0
    logger.info("Telegram Background Listener aktif.")
    while True:
        try:
            resp = requests.get(
                f"{tg_svc.base_url}/getUpdates",
                params={"offset": offset, "timeout": 15},
                timeout=20,
            )
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    handle_telegram_update(upd)
        except Exception:
            time.sleep(3)


def scheduled_evaluation_worker():
    time.sleep(10)
    while True:
        try:
            stores = db.list_stores()
            for s in stores:
                if s.active:
                    logger.info("Scheduler 3 Jam mengevaluasi toko %s", s.store_id)
                    orchestrator.evaluate_store(s.store_id, force_all=False)
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        time.sleep(10800)


@app.on_event("startup")
def start_background_tasks():
    t_tg = threading.Thread(target=telegram_polling_worker, daemon=True)
    t_tg.start()
    t_sched = threading.Thread(target=scheduled_evaluation_worker, daemon=True)
    t_sched.start()