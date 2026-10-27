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
        """
        Menjalankan evaluasi inventaris end-to-end dengan proteksi Distributed Lock
        agar satu toko tidak dievaluasi ganda pada detik yang sama.
        """
        store = self.db.get_store(store_id)
        if not store:
            raise ValueError(f"Toko {store_id} tidak ditemukan di database.")

        # P1 #11: Ambil lock evaluasi toko di DynamoDB
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

            now_dt = datetime.datetime.now()
            hari_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            day_name = hari_map[now_dt.weekday()]
            calendar_context = {
                "date": now_dt.strftime("%Y-%m-%d"),
                "day_name": day_name,
                "is_weekend": now_dt.weekday() >= 5,
                "is_payday": now_dt.day >= 25 or now_dt.day <= 5,
                "local_events": [e.model_dump() for e in store.local_events],
            }

            active_promos = [p.model_dump() for p in store.promos]
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
                req_id = f"REQ-{store.store_id}-{sku.sku_id}-{ts_int}"
                timeout_sec = store.timeout_tolerance_hours * 3600

                approval_state = TelegramApprovalState(
                    request_id=req_id,
                    store_id=store.store_id,
                    sku_id=sku.sku_id,
                    sku_name=sku.sku_name,
                    recommended_qty=final_recommended_qty,
                    status="PENDING_APPROVAL",
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                    expires_at=time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(ts_int + timeout_sec)
                    ),
                )
                self.db.save_approval_state(approval_state)

                target_chat = store.telegram_chat_id or config.TELEGRAM_DEFAULT_CHAT_ID
                tg_sent = False
                if target_chat and final_recommended_qty > 0:
                    tg_sent = self.tg_svc.send_recommendation_card(
                        chat_id=target_chat,
                        request_id=req_id,
                        store_name=store.store_name,
                        sku_name=sku.sku_name,
                        current_stock=sku.physical_stock,
                        recommended_qty=final_recommended_qty,
                        confidence=ai_rec.confidence_score,
                        reasoning=ai_rec.reasoning_narrative,
                        warnings=ai_rec.warnings,
                    )

                audit_entry = {
                    "request_id": req_id,
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
                    "telegram_sent": tg_sent,
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
