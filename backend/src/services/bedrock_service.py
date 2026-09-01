"""AWS Bedrock Reasoning Engine Integration with Claude 3.5 Sonnet.

Implements PRD Section 11.5, 12, 15.7, and 16:
- Multi-variable priority weighting.
- System prompt v1.0.
- Strict JSON schema enforcement with regex / parsing guardrails.
- Up to 2 retries on invalid output.
- Safe rule-based conservative fallback.
- Indonesian natural language reasoning narrative.
"""

import json
import re
import math
import logging
from typing import Dict, Any, Optional, Tuple
from ..config import logger, BEDROCK_MODEL_ID, MAX_BEDROCK_RETRIES, PROMPT_VERSION
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
8. If data is missing or cold start, be conservative and lower confidence score.

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
        self.client = bedrock_client
        self.model_id = model_id or BEDROCK_MODEL_ID
        self.prompt_version = PROMPT_VERSION

    def generate_recommendation(self, context: AggregationContext) -> AIRecommendationOutput:
        """Run context-aware reasoning via Bedrock with retries and fallback."""
        user_prompt = self._build_user_prompt(context)
        
        # If live Bedrock client is available, attempt invocation
        if self.client:
            for attempt in range(1 + MAX_BEDROCK_RETRIES):
                try:
                    logger.info(f"Invoking Bedrock model {self.model_id} (Attempt {attempt+1}) for SKU {context.sku.sku_id}")
                    raw_response = self._invoke_bedrock_api(user_prompt)
                    parsed = self._parse_and_validate_json(raw_response)
                    if parsed:
                        return parsed
                except Exception as e:
                    logger.warning(f"Bedrock invocation error (Attempt {attempt+1}): {e}")

        # Fallback to deterministic rule-based reasoning engine (PRD Section 15.7)
        logger.info(f"Executing deterministic rule-based reasoning for SKU {context.sku.sku_id}")
        return self._rule_based_fallback(context)

    def _build_user_prompt(self, context: AggregationContext) -> str:
        """Construct prompt payload conforming to Section 16.2."""
        feedback_str = f"\nRecent Store Feedback: {context.recent_feedback}" if context.recent_feedback else ""
        return f"""Store Context:
{json.dumps(context.store.to_dict(), indent=2)}

SKU Context:
{json.dumps(context.sku.to_dict(), indent=2)}{feedback_str}

External Context:
{json.dumps(context.external_context.to_dict(), indent=2)}

Based on the data above, calculate the optimal replenishment quantity. Explain the reasoning in Indonesian. Return strict JSON only."""

    def _invoke_bedrock_api(self, user_prompt: str) -> str:
        """Invoke Claude 3.5 Sonnet via Bedrock InvokeModel API."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.2,
            "system": SYSTEM_PROMPT_V1,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        })

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response.get("body").read())
        return response_body["content"][0]["text"]

    def _parse_and_validate_json(self, raw_text: str) -> Optional[AIRecommendationOutput]:
        """Validate and parse raw model response into structured recommendation."""
        # Strip potential markdown backticks
        clean_text = re.sub(r"^```json\s*", "", raw_text.strip())
        clean_text = re.sub(r"```$", "", clean_text.strip())

        try:
            data = json.loads(clean_text)
            # Validate required fields
            req_keys = ["recommended_qty", "confidence_score", "reasoning_narrative"]
            if not all(k in data for k in req_keys):
                return None

            return AIRecommendationOutput(
                recommended_qty=int(data.get("recommended_qty", 0)),
                normal_qty=int(data.get("normal_qty", 50)),
                adjusted_qty_before_moq=int(data.get("adjusted_qty_before_moq", data.get("recommended_qty", 0))),
                moq_applied=bool(data.get("moq_applied", False)),
                packaging_multiple_applied=bool(data.get("packaging_multiple_applied", False)),
                confidence_score=float(data.get("confidence_score", 0.85)),
                risk_level=data.get("risk_level", "medium"),
                reasoning_narrative=str(data.get("reasoning_narrative", "")),
                key_factors=data.get("key_factors", []),
                warnings=data.get("warnings", []),
                prompt_version=self.prompt_version,
                is_fallback=False
            )
        except Exception as e:
            logger.warning(f"JSON validation failed: {e}")
            return None

    def _rule_based_fallback(self, context: AggregationContext) -> AIRecommendationOutput:
        """
        High-fidelity deterministic rule-based calculation mimicking Bedrock multi-variable weights.
        Used for fallback, mock runs, and unit testing.
        """
        sku = context.sku
        store = context.store
        ext = context.external_context

        # 1. Base demand calculation: burn_rate * lead_time + safety buffer
        burn_rate = sku.average_daily_burn_rate
        lead_time = sku.lead_time_days
        base_demand = burn_rate * (lead_time + 1)
        deficit = max(0, int(base_demand - (sku.physical_stock + sku.open_pr_qty)))

        normal_qty = int(burn_rate * (lead_time + 2))
        
        # 2. Context Modifiers
        modifier = 1.0
        key_factors = []
        warnings = []
        is_perishable = sku.category.lower() == "perishable"

        # Check deficit vs threshold
        if sku.physical_stock < sku.threshold:
            key_factors.append("below_threshold")

        # Promo Factor (15-20%)
        if ext.promo.is_active:
            modifier *= ext.promo.multiplier_factor
            key_factors.append(f"promo_active_{ext.promo.promo_type}")

        # Calendar & Area Demographics Factor (5-10%)
        if store.area_type.lower() == "perkantoran":
            if ext.calendar.day_type == "Weekend":
                # Offices are quiet on weekends
                modifier *= 0.40
                key_factors.append("weekend_office_area_quiet")
                if is_perishable:
                    warnings.append("Permintaan weekend berisiko lebih rendah dari estimasi normal")
            else:
                modifier *= 1.15
        elif store.area_type.lower() == "perumahan":
            if ext.calendar.day_type == "Weekend":
                modifier *= 1.30
                key_factors.append("weekend_residential_busy")

        # Weather Factor (10-15%)
        if "hujan" in ext.weather.condition.lower() or ext.weather.rain_probability > 0.6:
            key_factors.append("heavy_rain")
            if is_perishable and store.area_type.lower() == "perkantoran":
                modifier *= 0.70
                key_factors.append("rain_reduces_office_traffic")
            elif not is_perishable:
                modifier *= 0.95

        # Payday Effect
        if ext.calendar.is_payday:
            modifier *= 1.15
            key_factors.append("payday_uplift")

        # Cold Start Handling
        confidence = 0.88
        risk_level = "medium"
        if sku.is_cold_start:
            key_factors.append("cold_start_benchmark")
            warnings.append("SKU baru dengan data histori penjualan terbatas")
            confidence = 0.65
            risk_level = "high"

        # Calculate Raw Recommended Qty
        raw_recommended = max(1, int(round(deficit * modifier))) if deficit > 0 else 0

        # Construct Indonesian Narrative
        if is_perishable and store.area_type.lower() == "perkantoran" and ext.calendar.day_type == "Weekend":
            narrative = (
                f"Stok di bawah threshold ({sku.physical_stock}/{sku.threshold} pcs), "
                f"namun area {store.area_type.lower()} sepi saat weekend dan cuaca {ext.weather.condition.lower()} "
                f"menurunkan kunjungan. Kuota disesuaikan ke {raw_recommended} pcs untuk mencegah overstock dan kedaluwarsa."
            )
            warnings.append(f"SKU perishable dengan lead time {sku.lead_time_days} hari")
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
