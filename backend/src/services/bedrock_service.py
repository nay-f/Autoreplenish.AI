import time
import math
import json
import logging
import boto3
import backend.src.config as config
from backend.src.models.schema import StoreProfile, SKUItem, AIRecommendation

logger = logging.getLogger("autoreplenish.bedrock")


class BedrockReasoningService:
    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=config.AWS_REGION,
        )
        self.model_id = config.BEDROCK_MODEL_ID
        self.prompt_version = config.PROMPT_VERSION

    @staticmethod
    def calculate_deterministic_baseline(sku: SKUItem) -> dict:
        """
        Menghitung kebutuhan stok dasar secara matematis (deterministik) di Python
        sebelum disesuaikan oleh penalaran kontekstual AI.
        """
        stock_deficit = max(sku.threshold - sku.physical_stock, 0)
        lead_time_demand = math.ceil(sku.average_daily_burn_rate * max(sku.lead_time_days, 1))
        baseline_qty = stock_deficit + lead_time_demand

        # Batas atas dan bawah yang diizinkan untuk penyesuaian AI
        max_cap = max(int(math.ceil(baseline_qty * config.AI_MAX_MULTIPLIER_CAP)), sku.moq * 2)
        min_floor = int(math.floor(baseline_qty * config.AI_MIN_MULTIPLIER_FLOOR)) if baseline_qty > 0 else 0

        return {
            "stock_deficit": stock_deficit,
            "lead_time_demand": lead_time_demand,
            "baseline_qty": baseline_qty,
            "min_allowed_qty": min_floor,
            "max_allowed_qty": max_cap,
        }

    def generate_recommendation(
        self,
        store: StoreProfile,
        sku: SKUItem,
        weather: dict,
        calendar_context: dict,
        active_promos: list = None,
    ) -> AIRecommendation:
        """
        Mengevaluasi stok dengan arsitektur Hybrid:
        Deterministic Baseline (Python) + Contextual Reasoning (Bedrock) + Safety Guardrail (Python).
        """
        start_time = time.time()
        baseline_info = self.calculate_deterministic_baseline(sku)
        baseline_qty = baseline_info["baseline_qty"]
        min_allowed = baseline_info["min_allowed_qty"]
        max_allowed = baseline_info["max_allowed_qty"]

        system_prompt = (
            f"Anda adalah AutoReplenish.ai (Prompt Version: {self.prompt_version}), "
            "asisten pengadaan untuk staf toko dan manajer operasional.\n"
            "Gunakan kondisi stok, kecepatan pemakaian, waktu pengiriman, cuaca, promo, "
            "dan kalender untuk menyesuaikan jumlah pesanan yang aman.\n\n"
            "ATURAN MUTLAK:\n"
            f"1. Rentang 'recommended_qty' yang diizinkan berada di antara {min_allowed} hingga {max_allowed} unit.\n"
            "2. Jika barang mudah rusak dan permintaan diperkirakan rendah, turunkan rekomendasi secara konservatif.\n"
            "3. Balas HANYA dengan JSON VALID murni tanpa blok markdown ```json.\n"
            "4. Tulis reasoning_narrative dan warnings dalam bahasa Indonesia sehari-hari, singkat, jelas, dan mudah dipahami staf toko.\n"
            "5. reasoning_narrative maksimal 3 kalimat pendek. Jelaskan sisa stok cukup berapa lama, pengaruh cuaca/hari gajian bila relevan, serta jumlah usulan cukup untuk berapa lama.\n"
            "6. Jangan gunakan istilah teknis seperti deterministik, Pareto, baseline, unconstrained, bobot persentase, atau burn rate.\n"
            "7. Jangan menyebut confidence_score sebagai akurasi atau jaminan.\n\n"
            "Skema JSON Wajib:\n"
            "{\n"
            '  "recommended_qty": integer,\n'
            '  "confidence_score": float (0.0 - 1.0),\n'
            '  "risk_level": "low" | "medium" | "high",\n'
            '  "reasoning_narrative": "string penjelasan sebab-akibat",\n'
            '  "key_factors": ["faktor1", "faktor2"],\n'
            '  "warnings": ["peringatan1"]\n'
            "}"
        )

        user_context = {
            "deterministic_calculation": baseline_info,
            "store": {
                "name": store.store_name,
                "area_type": store.area_type,
                "zone": store.zone,
            },
            "sku": {
                "name": sku.sku_name,
                "category": sku.category,
                "current_stock": sku.physical_stock,
                "safety_threshold": sku.threshold,
                "daily_burn_rate": sku.average_daily_burn_rate,
                "lead_time_days": sku.lead_time_days,
                "is_perishable": sku.is_perishable,
                "shelf_life_days": sku.shelf_life_days,
            },
            "external_signals": {
                "weather": weather,
                "calendar": calendar_context,
                "active_promos": active_promos or [],
            },
        }

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.15,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": f"Evaluasi konteks inventaris berikut dan hasilkan JSON keputusan:\n{json.dumps(user_context, indent=2)}",
                }
            ],
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )
            latency_ms = int((time.time() - start_time) * 1000)
            response_body = json.loads(response["body"].read().decode("utf-8"))
            raw_text = response_body["content"][0]["text"].strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            raw_text = raw_text.strip()

            parsed = json.loads(raw_text)
            ai_raw_qty = int(parsed.get("recommended_qty", baseline_qty))
            confidence = float(parsed.get("confidence_score", 0.75))
            warnings = list(parsed.get("warnings", []))
            guardrail_applied = False
            constrained_qty = ai_raw_qty

            # P1 #17: Terapkan Guardrail Batas Atas & Bawah
            if constrained_qty > max_allowed:
                constrained_qty = max_allowed
                guardrail_applied = True
                warnings.append(
                    f"Guardrail aktif: Rekomendasi AI ({ai_raw_qty}) dipangkas ke batas aman maksimum ({max_allowed} unit)."
                )
            elif constrained_qty < min_allowed and ai_raw_qty > 0:
                constrained_qty = min_allowed
                guardrail_applied = True
                warnings.append(
                    f"Guardrail aktif: Rekomendasi AI ({ai_raw_qty}) dinaikkan ke batas minimum operasional ({min_allowed} unit)."
                )

            # P1 #19: Terapkan Kebijakan Confidence Threshold
            if confidence >= config.CONFIDENCE_HIGH_THRESHOLD:
                confidence_tier = "HIGH_CONFIDENCE"
            elif confidence >= config.CONFIDENCE_MIN_ACCEPTABLE:
                confidence_tier = "MANUAL_REVIEW_REQUIRED"
                warnings.append("Confidence moderat (60%-84%): Wajib verifikasi Kepala Toko.")
            else:
                confidence_tier = "LOW_CONFIDENCE_GUARDRAILED"
                constrained_qty = baseline_qty
                guardrail_applied = True
                warnings.append(
                    f"Confidence rendah ({confidence*100:.0f}% < 60%): Kuota dikembalikan ke baseline deterministik ({baseline_qty} unit)."
                )

            return AIRecommendation(
                recommended_qty=constrained_qty,
                normal_qty=baseline_qty,
                deterministic_baseline_qty=baseline_qty,
                ai_unconstrained_qty=ai_raw_qty,
                adjusted_qty_before_moq=constrained_qty,
                confidence_score=confidence,
                confidence_tier=confidence_tier,
                risk_level=parsed.get("risk_level", "medium"),
                reasoning_narrative=parsed.get("reasoning_narrative", "Penalaran selesai."),
                key_factors=parsed.get("key_factors", []),
                warnings=warnings,
                guardrail_applied=guardrail_applied,
                is_fallback=False,
                model_id=self.model_id,
                prompt_version=self.prompt_version,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            failure_class = self._classify_failure(e)
            logger.error(
                "Bedrock %s (%s), mengaktifkan deterministic fallback.",
                failure_class,
                e,
            )
            return AIRecommendation(
                recommended_qty=baseline_qty,
                normal_qty=baseline_qty,
                deterministic_baseline_qty=baseline_qty,
                ai_unconstrained_qty=baseline_qty,
                adjusted_qty_before_moq=baseline_qty,
                confidence_score=0.60,
                confidence_tier="LOW_CONFIDENCE_GUARDRAILED",
                risk_level="medium",
                reasoning_narrative=(
                    f"- Stok tersisa {sku.physical_stock} unit dengan perkiraan kebutuhan "
                    f"{baseline_info['lead_time_demand']} unit selama waktu pengiriman {sku.lead_time_days} hari.\n"
                    f"- Usulan sementara {baseline_qty} unit dibuat agar pasokan tetap tersedia "
                    "sambil menunggu pemeriksaan manusia."
                ),
                key_factors=["deterministic_baseline_fallback"],
                warnings=[
                    f"Mode fallback deterministik aktif ({failure_class}). Wajib verifikasi manusia."
                ],
                guardrail_applied=True,
                is_fallback=True,
                model_id=self.model_id,
                prompt_version=self.prompt_version,
                latency_ms=latency_ms,
                failure_class=failure_class,
            )

    @staticmethod
    def _classify_failure(error: Exception) -> str:
        """Return an operational category without exposing provider details."""
        name = type(error).__name__.lower()
        message = str(error).lower()
        if "accessdenied" in name or "access denied" in message:
            return "BEDROCK_AUTHORIZATION_ERROR"
        if "validation" in name or "validationexception" in message:
            return "BEDROCK_OUTPUT_OR_REQUEST_VALIDATION_ERROR"
        if "json" in name or "json" in message:
            return "BEDROCK_INVALID_JSON"
        if "timeout" in name or "timeout" in message:
            return "BEDROCK_TIMEOUT"
        return "BEDROCK_INVOCATION_ERROR"
