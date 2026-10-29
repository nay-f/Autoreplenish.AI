import time
import datetime
import logging
import backend.src.config as config
from backend.src.models.schema import TelegramApprovalState
from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.services.weather_service import WeatherService
from backend.src.services.bedrock_service import BedrockReasoningService
from backend.src.services.moq_packaging_service import MOQPackagingService
from backend.src.services.telegram_service import TelegramService

logger = logging.getLogger("autoreplenish.orchestrator")


class OrchestratorService:
    def __init__(self):
        self.db = DynamoDBService()
        self.weather_svc = WeatherService(self.db)
        self.ai_svc = BedrockReasoningService()
        self.tg_svc = TelegramService(self.db)

    def evaluate_store(self, store_id: str, force_all: bool = False) -> dict:
        """Evaluate inventory and send approval cards, protected by a store lock."""
        store = self.db.get_store(store_id)
        if not store:
            raise ValueError(f"Toko {store_id} tidak ditemukan di database.")

        if not self.db.acquire_store_eval_lock(store_id, lock_ttl_seconds=90):
            logger.info("Evaluasi toko %s dilewati karena proses evaluasi lain sedang berjalan.", store_id)
            return {
                "store_id": store.store_id,
                "store_name": store.store_name,
                "evaluated_count": 0,
                "skipped_locked": True,
                "message": "Evaluasi untuk toko ini sedang berjalan di proses lain. Silakan tunggu beberapa detik.",
                "results": [],
            }

        try:
            skus = self.db.get_skus_for_store(store_id)
            if not skus:
                return {
                    "store_id": store_id,
                    "store_name": store.store_name,
                    "evaluated_count": 0,
                    "message": "Belum ada SKU yang terdaftar di toko ini.",
                    "results": [],
                }

            weather = self.weather_svc.get_weather_for_store(store)
            now_dt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
            hari_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            calendar_context = {
                "date": now_dt.strftime("%Y-%m-%d"),
                "day_name": hari_map[now_dt.weekday()],
                "is_weekend": now_dt.weekday() >= 5,
                "is_payday": now_dt.day >= 25 or now_dt.day <= 5,
                "local_events": [event.model_dump() for event in store.local_events],
            }
            active_promos = [promo.model_dump() for promo in store.promos]
            results = []

            for sku in skus:
                if not force_all and sku.physical_stock > sku.threshold:
                    continue
                ai_rec = self.ai_svc.generate_recommendation(
                    store=store,
                    sku=sku,
                    weather=weather,
                    calendar_context=calendar_context,
                    active_promos=active_promos,
                )
                moq_adj = MOQPackagingService.adjust_quantity(
                    sku=sku,
                    ai_qty=ai_rec.recommended_qty,
                    risk_level=ai_rec.risk_level,
                )
                final_recommended_qty = moq_adj["final_qty"]
                ts_int = int(time.time())
                request_id = f"REQ-{store.store_id}-{sku.sku_id}-{ts_int}"
                timeout_sec = store.timeout_tolerance_hours * 3600
                approval_state = TelegramApprovalState(
                    request_id=request_id,
                    store_id=store.store_id,
                    sku_id=sku.sku_id,
                    sku_name=sku.sku_name,
                    recommended_qty=final_recommended_qty,
                    status="PENDING_APPROVAL",
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                    expires_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_int + timeout_sec)),
                )
                self.db.save_approval_state(approval_state)
                target_chat = store.telegram_chat_id or config.TELEGRAM_DEFAULT_CHAT_ID
                telegram_sent = False
                if target_chat and final_recommended_qty > 0:
                    telegram_sent = self.tg_svc.send_recommendation_card(
                        chat_id=target_chat,
                        request_id=request_id,
                        store_name=store.store_name,
                        sku_name=sku.sku_name,
                        current_stock=sku.physical_stock,
                        recommended_qty=final_recommended_qty,
                        confidence=ai_rec.confidence_score,
                        reasoning=ai_rec.reasoning_narrative,
                        warnings=ai_rec.warnings,
                        daily_burn_rate=sku.average_daily_burn_rate,
                        threshold=sku.threshold,
                        lead_time_days=sku.lead_time_days,
                        packaging_multiple=sku.packaging_multiple,
                        is_fallback=ai_rec.is_fallback,
                    )

                audit_entry = {
                    "request_id": request_id,
                    "store_name": store.store_name,
                    "sku_name": sku.sku_name,
                    "physical_stock": sku.physical_stock,
                    "threshold": sku.threshold,
                    "weather_snapshot": weather,
                    "calendar_snapshot": calendar_context,
                    "deterministic_baseline_qty": ai_rec.deterministic_baseline_qty,
                    "ai_unconstrained_qty": ai_rec.ai_unconstrained_qty,
                    "ai_raw_qty": ai_rec.recommended_qty,
                    "final_recommended_qty": final_recommended_qty,
                    "moq_note": moq_adj["note"],
                    "confidence_score": ai_rec.confidence_score,
                    "confidence_tier": ai_rec.confidence_tier,
                    "risk_level": ai_rec.risk_level,
                    "reasoning_narrative": ai_rec.reasoning_narrative,
                    "warnings": ai_rec.warnings,
                    "guardrail_applied": ai_rec.guardrail_applied,
                    "is_fallback": ai_rec.is_fallback,
                    "bedrock_failure_class": ai_rec.failure_class,
                    "evaluation_status": "DETERMINISTIC_FALLBACK" if ai_rec.is_fallback else "BEDROCK_SUCCESS",
                    "model_id": ai_rec.model_id,
                    "prompt_version": ai_rec.prompt_version,
                    "rule_engine_version": config.RULE_ENGINE_VERSION,
                    "latency_ms": ai_rec.latency_ms,
                    "telegram_sent": telegram_sent,
                    "approval_status": "PENDING_APPROVAL",
                }
                self.db.save_audit_log(
                    store_id=store.store_id,
                    timestamp_str=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    sku_id=sku.sku_id,
                    audit_data=audit_entry,
                )
                results.append(audit_entry)

            return {
                "store_id": store.store_id,
                "store_name": store.store_name,
                "evaluated_count": len(results),
                "weather": weather,
                "results": results,
            }
        finally:
            self.db.release_store_eval_lock(store_id)

    def generate_and_send_daily_recap(self, store_id: str, trigger_source: str = "SCHEDULED") -> dict:
        """Build and send current stock and approval recap, using WIB timestamps."""
        now_wib = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
        timestamp = now_wib.strftime("%d %b %Y | %H:%M WIB")
        store = self.db.get_store(store_id)
        if not store:
            raise ValueError(f"Toko {store_id} tidak ditemukan.")

        skus = self.db.get_skus_for_store(store_id)
        critical = [sku for sku in skus if sku.physical_stock <= sku.threshold]
        approvals = self.db.get_approval_states_for_store(store_id)
        day_start_wib = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_utc = day_start_wib.astimezone(datetime.timezone.utc)
        next_day_utc = (day_start_wib + datetime.timedelta(days=1)).astimezone(datetime.timezone.utc)
        approvals = [
            item for item in approvals
            if item.created_at
            and day_start_utc <= datetime.datetime.strptime(item.created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc) < next_day_utc
        ]
        approved_statuses = {
            "APPROVED", "ENQUEUED", "SAP_SUBMITTING", "SAP_SUBMITTED",
            "SAP_SANDBOX_VERIFIED", "SAP_DRY_RUN",
        }
        approved = [item for item in approvals if item.status in approved_statuses]
        pending = [item for item in approvals if item.status == "PENDING_APPROVAL"]
        rejected = [item for item in approvals if item.status == "REJECTED"]
        sku_by_id = {sku.sku_id: sku for sku in skus}
        value = sum(
            item.recommended_qty * getattr(sku_by_id.get(item.sku_id), "unit_price", 0)
            for item in approved
        )
        details = "\n".join(
            f"• {sku.sku_name}: sisa {sku.physical_stock} Pcs (batas aman {sku.threshold})"
            for sku in critical[:5]
        ) or "Semua stok berada di atas batas aman."
        mode = "Manual Telegram" if trigger_source == "MANUAL" else "Jadwal otomatis"
        recap = (
            "📊 <b>REKAP HARIAN PENGADAAN</b>\n"
            f"🕒 {timestamp} · {mode}\n"
            f"🏪 {store.store_name}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Dipantau: {len(skus)} SKU · Aman: {len(skus) - len(critical)} · Kritis: {len(critical)}\n"
            f"✅ Disetujui/diproses: {len(approved)} · ⏳ Menunggu: {len(pending)} · ❌ Ditolak: {len(rejected)}\n"
            f"💰 Perkiraan nilai: Rp {int(value):,}\n\n"
            f"⚠️ <b>Stok kritis</b>\n{details}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\nKetik /recap untuk ringkasan atau /evaluasi untuk evaluasi AI."
        )
        if store.telegram_chat_id:
            self.tg_svc.send_text(str(store.telegram_chat_id), recap)

        return {
            "store_id": store_id,
            "timestamp_wib": timestamp,
            "total_skus": len(skus),
            "critical_count": len(critical),
            "approved_count": len(approved),
            "pending_count": len(pending),
            "rejected_count": len(rejected),
            "estimated_value_rp": value,
        }
