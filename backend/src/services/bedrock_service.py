"""AWS Bedrock Reasoning Engine Integration with Claude 3.5 Sonnet.

Implements PRD Section 11.5, 12, 15.7, and 16:
- Multi-variable priority weighting.
- System prompt v1.0.
- Strict JSON schema enforcement with regex / parsing guardrails.
- Up to 2 retries on invalid output.
- Safe rule-based conservative fallback (ONLY on Bedrock exception) flagged
  with ``is_fallback=True`` so the audit trail never presents a simulated
  recommendation as a genuine model output (PRD Section 11.12).
"""

import json
import re
from typing import Dict, Any, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from ..config import (
    logger,
    BEDROCK_MODEL_ID,
    MAX_BEDROCK_RETRIES,
    PROMPT_VERSION,
    BEDROCK_MAX_TOKENS,
    BEDROCK_TEMPERATURE,
    AWS_REGION,
)
from ..models.schema import (
    AggregationContext,
    AIRecommendationOutput,
)

SYSTEM_PROMPT_V1 = """You are AutoReplenish.ai, an Agentic AI assistant for minimarket replenishment.

Your job is to recommend optimal replenishment quantity for a specific SKU at a specific store. You must reason based on inventory, supplier lead time, promotions, weather, calendar effects, and store demographics.

You are not allowed to create final business documents directly. Your output is a recommendation for human approval.

Use Indonesian for the reasoning narrative. Be concise, practical, and clear.

Output must be strict valid JSON only. Do not include markdown (no ```json codeblocks), explanations outside JSON, or comments.

Decision principles:
1. Prevent stockout when demand until next delivery is likely to exceed available stock.
2. Prevent overstock and spoilage, especially for perishable items.
3. Consider supplier lead time and next delivery schedule.
4. Consider active promotions.
5. Consider weather and temperature effects.
6. Consider weekday, weekend, payday, and public holiday effects.
7. Respect MOQ and packaging multiple.
8. Respect shelf life: never recommend quantities that cannot sell through before expiry.
9. If data is missing or cold start, be conservative and lower confidence score.

Variable priority:
- Stock and sales history: 35% - 40%
- Supplier schedule and lead time: 20% - 25%
- Internal promo catalog: 15% - 20%
- Weather and temperature: 10% - 15%
- Time cycle and calendar: 5% - 10%

Return JSON using this schema:
{
  "recommended_qty": integer,
  "normal_qty": integer,
  "adjusted_qty_before_moq": integer,
  "moq_applied": boolean,
  "packaging_multiple_applied": boolean,
  "confidence_score": number between 0 and 1,
  "risk_level": "low" | "medium" | "high",
  "reasoning_narrative": string,
  "key_factors": array of strings,
  "warnings": array of strings
}
"""


class BedrockReasoningService:
    """Reasoning engine integrating AWS Bedrock Claude 3.5 Sonnet."""

    def __init__(self, bedrock_client: Optional[Any] = None, model_id: Optional[str] = None):
        """
        Args:
            bedrock_client: Injectable ``boto3.client('bedrock-runtime')``.
                When omitted, a real client is constructed for the configured region.
            model_id: Overrides config.BEDROCK_MODEL_ID.
        """
        self.model_id = model_id or BEDROCK_MODEL_ID
        self.prompt_version = PROMPT_VERSION
        self._client_injected = bedrock_client is not None
        self.client = bedrock_client or boto3.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
            config=BotoConfig(
                read_timeout=60,
                connect_timeout=10,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def generate_recommendation(self, context: AggregationContext) -> AIRecommendationOutput:
        """Run context-aware reasoning via Bedrock.

        The deterministic rule-based engine is reached ONLY when every Bedrock
        attempt fails (quota exhaustion, throttling, timeout, malformed output).
        The fallback is always marked ``is_fallback=True``.
        """
        user_prompt = self._build_user_prompt(context)
        last_error: Optional[str] = None

        for attempt in range(1 + MAX_BEDROCK_RETRIES):
            try:
                logger.info(
                    f"Invoking Bedrock model {self.model_id} "
                    f"(attempt {attempt + 1}/{1 + MAX_BEDROCK_RETRIES}) "
                    f"for SKU {context.sku.sku_id}"
                )
                raw_response = self._invoke_bedrock_api(user_prompt)
                parsed = self._parse_and_validate_json(raw_response)
                if parsed:
                    parsed.is_fallback = False
                    return parsed
                last_error = "Bedrock returned JSON that failed schema validation"
                logger.warning(f"{last_error} (attempt {attempt + 1})")
            except (ClientError, BotoCoreError) as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(f"Bedrock invocation error (attempt {attempt + 1}): {last_error}")
            except Exception as e:  # defensive: never let the reasoning step kill the run
                last_error = f"Unexpected {type(e).__name__}: {e}"
                logger.warning(f"Unexpected reasoning error (attempt {attempt + 1}): {last_error}")

        logger.error(
            f"Bedrock unavailable for SKU {context.sku.sku_id} after "
            f"{1 + MAX_BEDROCK_RETRIES} attempts ({last_error}). "
            f"Engaging deterministic rule-based fallback (PRD 15.7)."
        )
        return self._rule_based_fallback(context, reason=last_error)

    def build_invocation_payload(self, user_prompt: str) -> Dict[str, Any]:
        """Expose the Anthropic Messages body for tests/observability."""
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": BEDROCK_MAX_TOKENS,
            "temperature": BEDROCK_TEMPERATURE,
            "system": SYSTEM_PROMPT_V1,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }

    def _build_user_prompt(self, context: AggregationContext) -> str:
        """Construct prompt payload conforming to Section 16.2."""
        feedback_str = f"\nRecent Store Feedback: {context.recent_feedback}" if context.recent_feedback else ""
        return f"""Store Context:
{json.dumps(context.store.to_dict(), indent=2, ensure_ascii=False)}

SKU Context:
{json.dumps(context.sku.to_dict(), indent=2, ensure_ascii=False)}{feedback_str}

External Context:
{json.dumps(context.external_context.to_dict(), indent=2, ensure_ascii=False)}

Based on the data above, calculate the optimal replenishment quantity. Explain the reasoning in Indonesian. Return strict JSON only."""

    def _invoke_bedrock_api(self, user_prompt: str) -> str:
        """Invoke Claude 3.5 Sonnet via the Bedrock InvokeModel API."""
        body = json.dumps(self.build_invocation_payload(user_prompt))

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response.get("body").read())
        content = response_body.get("content") or []
        if not content:
            raise ValueError("Bedrock response contained no content blocks")

        text = content[0].get("text", "")
        if not text.strip():
            raise ValueError("Bedrock response contained an empty content block")
        return text

    def _parse_and_validate_json(self, raw_text: str) -> Optional[AIRecommendationOutput]:
        """Validate and parse raw model response into structured recommendation."""
        # Strip potential markdown backticks
        clean_text = re.sub(r"^```json\s*", "", raw_text.strip())
        clean_text = re.sub(r"```$", "", clean_text.strip())

        try:
            data = json.loads(clean_text)
        except Exception as e:
            logger.warning(f"JSON decode failed: {e}")
            return None

        # Validate required fields
        req_keys = ["recommended_qty", "confidence_score", "reasoning_narrative"]
        if not all(k in data for k in req_keys):
            logger.warning("Bedrock JSON missing one or more required keys")
            return None

        try:
            return AIRecommendationOutput(
                recommended_qty=int(data.get("recommended_qty", 0)),
                normal_qty=int(data.get("normal_qty", 50)),
                adjusted_qty_before_moq=int(data.get("adjusted_qty_before_moq", data.get("recommended_qty", 0))),
                moq_applied=bool(data.get("moq_applied", False)),
                packaging_multiple_applied=bool(data.get("packaging_multiple_applied", False)),
                confidence_score=self._clamp(float(data.get("confidence_score", 0.85)), 0.0, 1.0),
                risk_level=str(data.get("risk_level", "medium")).lower(),
                reasoning_narrative=str(data.get("reasoning_narrative", "")),
                key_factors=list(data.get("key_factors", [])),
                warnings=list(data.get("warnings", [])),
                prompt_version=self.prompt_version,
                is_fallback=False
            )
        except Exception as e:
            logger.warning(f"Schema coercion failed: {e}")
            return None

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    # ---------------------------------------------------------
    # Deterministic fallback (PRD Section 15.7)
    # ---------------------------------------------------------
    def _rule_based_fallback(
        self,
        context: AggregationContext,
        reason: Optional[str] = None
    ) -> AIRecommendationOutput:
        """
        High-fidelity deterministic rule-based calculation used ONLY when Bedrock
        is unavailable. Always returns ``is_fallback=True`` and records a warning
        so downstream consumers (Telegram card, audit trail) disclose the degraded
        reasoning mode to the store manager.
        """
        sku = context.sku
        store = context.store
        ext = context.external_context

        key_factors: list = []
        warnings: list = []

        # 1. Base demand calculation: burn_rate * (lead_time + 1) + safety buffer
        burn_rate = max(0.0, sku.average_daily_burn_rate)
        lead_time = max(1, sku.lead_time_days)
        base_demand = burn_rate * (lead_time + 1)
        deficit = max(0, int(base_demand - (sku.physical_stock + sku.open_pr_qty)))

        normal_qty = int(burn_rate * (lead_time + 2))

        modifier = 1.0
        is_perishable = sku.category.lower() == "perishable"
        area = (store.area_type or "").lower()

        if sku.physical_stock < sku.threshold:
            key_factors.append("below_threshold")

        # 2. Shelf-life guardrail: never order more than can sell before expiry
        max_sellable = int(burn_rate * max(1, sku.shelf_life_days)) if burn_rate > 0 else 0

        # 3. Promo Factor (15-20%)
        if ext.promo.is_active:
            modifier *= ext.promo.multiplier_factor
            key_factors.append(f"promo_active_{ext.promo.promo_type}")

        # 4. Calendar & Area Demographics Factor (5-10%)
        if "perkantoran" in area:
            if ext.calendar.day_type == "Weekend":
                modifier *= 0.40
                key_factors.append("weekend_office_area_quiet")
            else:
                modifier *= 1.15
                key_factors.append("weekday_office_traffic")
        elif "perumahan" in area or "pemukiman" in area or "sub-urban" in area or "suburban" in area:
            if ext.calendar.day_type == "Weekend":
                modifier *= 1.30
                key_factors.append("weekend_residential_busy")
            else:
                modifier *= 1.05
        elif "kampus" in area:
            if ext.calendar.day_type == "Weekend":
                modifier *= 0.70
                key_factors.append("weekend_campus_quiet")

        # 5. Weather Factor (10-15%)
        if "hujan" in ext.weather.condition.lower() or ext.weather.rain_probability > 0.6:
            key_factors.append("heavy_rain")
            if is_perishable and ("perkantoran" in area or "kampus" in area):
                modifier *= 0.70
                key_factors.append("rain_reduces_foot_traffic")
            elif not is_perishable:
                modifier *= 0.95

        # 6. Payday Effect
        if ext.calendar.is_payday:
            modifier *= 1.15
            key_factors.append("payday_uplift")

        # 7. Fragile / short shelf-life guardrails
        if sku.is_fragile:
            key_factors.append("fragile_handling_required")
            modifier *= 0.90
        if is_perishable and sku.shelf_life_days <= 3:
            key_factors.append(f"short_shelf_life_{sku.shelf_life_days}d")
            modifier *= 0.80
            warnings.append(
                f"Shelf life hanya {sku.shelf_life_days} hari - risiko kedaluwarsa tinggi jika kuota berlebih"
            )

        # 8. Calculate Raw Recommended Qty with shelf-life ceiling
        raw_recommended = max(1, int(round(deficit * modifier))) if deficit > 0 else 0
        if max_sellable > 0 and raw_recommended > max_sellable:
            key_factors.append("capped_by_shelf_life")
            raw_recommended = max(1, max_sellable)
            warnings.append("Kuota dibatasi maksimum terlaris sebelum kedaluwarsa")

        # 9. Cold Start Handling
        confidence = 0.88
        risk_level = "medium"
        if sku.is_cold_start:
            key_factors.append("cold_start_benchmark")
            warnings.append("SKU baru dengan data histori penjualan terbatas")
            confidence = 0.65
            risk_level = "high"

        # 10. Indonesian Narrative
        if is_perishable and "perkantoran" in area and ext.calendar.day_type == "Weekend":
            narrative = (
                f"Stok di bawah threshold ({sku.physical_stock}/{sku.threshold} pcs), "
                f"namun area perkantoran sepi saat weekend dan cuaca {ext.weather.condition.lower()} "
                f"menurunkan kunjungan. Kuota disesuaikan ke {raw_recommended} pcs untuk mencegah overstock dan kedaluwarsa."
            )
        elif ext.promo.is_active:
            narrative = (
                f"Stok mendekati threshold dengan promo aktif {ext.promo.promo_name}. "
                f"Kuota dinaikkan untuk mengantisipasi lonjakan permintaan promo."
            )
        else:
            narrative = (
                f"Stok ({sku.physical_stock} pcs) membutuhkan replenishment berdasarkan rata-rata konsumsi harian "
                f"({burn_rate:.1f} pcs/hari) dan lead time {sku.lead_time_days} hari."
            )

        if reason:
            warnings.insert(0, f"Mode penalaran fallback deterministik aktif ({reason})")

        return AIRecommendationOutput(
            recommended_qty=raw_recommended,
            normal_qty=normal_qty,
            adjusted_qty_before_moq=raw_recommended,
            moq_applied=False,
            packaging_multiple_applied=False,
            confidence_score=confidence,
            risk_level=risk_level,
            reasoning_narrative=narrative,
            key_factors=key_factors,
            warnings=warnings,
            prompt_version=self.prompt_version,
            is_fallback=True
        )
