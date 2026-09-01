"""Orchestrator Service for Scheduled SKU Evaluation & Replenishment Pipeline.

Implements PRD Section 9, 10, 11.1 (FR-01), 11.2 (FR-02), 11.3 (FR-03), and 11.12 (FR-12).
"""

import time
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from ..config import logger, APPROVAL_TIMEOUT_HOURS
from ..models.schema import (
    StoreProfile,
    SKUProfile,
    SKUContext,
    ExternalContext,
    AggregationContext,
    PrioritySKU,
    PrioritizationOutput,
    AIRecommendationOutput,
    TelegramStateRecord,
    AuditLogRecord,
)
from .dynamodb_service import DynamoDBService
from .weather_service import WeatherService
from .calendar_promo_service import CalendarPromoService
from .bedrock_service import BedrockReasoningService
from .moq_packaging_service import MoqPackagingService
from .telegram_service import TelegramService

class OrchestratorService:
    """End-to-End Replenishment Pipeline Orchestrator."""

    def __init__(
        self,
        db_service: DynamoDBService,
        weather_service: WeatherService,
        calendar_promo_service: CalendarPromoService,
        bedrock_service: BedrockReasoningService,
        telegram_service: TelegramService
    ):
        self.db = db_service
        self.weather = weather_service
        self.calendar_promo = calendar_promo_service
        self.bedrock = bedrock_service
        self.telegram = telegram_service

    def prioritize_skus(
        self,
        store: StoreProfile,
        skus: List[SKUProfile],
        stock_levels: Dict[str, Dict[str, Any]]
    ) -> List[PrioritySKU]:
        """
        Evaluate and prioritize SKUs using the 8 criteria from PRD Section 11.2.
        """
        priority_list = []

        for sku in skus:
            stock_info = stock_levels.get(sku.sku_id, {
                "physical_stock": 10,
                "threshold": 20,
                "average_daily_burn_rate": 15.0,
                "lead_time_days": sku.default_lead_time_days,
                "open_pr_qty": 0,
                "is_cold_start": False
            })

            physical_stock = stock_info["physical_stock"]
            threshold = stock_info["threshold"]
            burn_rate = stock_info["average_daily_burn_rate"]
            lead_time = stock_info["lead_time_days"]
            is_cold_start = stock_info.get("is_cold_start", False)

            score = 0
            reason_codes = []

            # 1. Physical stock below threshold
            if physical_stock < threshold:
                deficit_ratio = (threshold - physical_stock) / threshold
                score += int(35 + (deficit_ratio * 20))
                reason_codes.append("below_threshold")

            # 2. Perishable category
            if sku.category.lower() == "perishable":
                score += 20
                reason_codes.append("perishable")

            # 3. Weather sensitive
            if sku.weather_sensitive:
                score += 15
                reason_codes.append("weather_sensitive")

            # 4. Active Promo
            promo_context = self.calendar_promo.get_promo_context(sku.sku_id)
            if promo_context.is_active:
                score += 20
                reason_codes.append("promo_active")

            # 5. High burn rate
            if burn_rate >= 20:
                score += 15
                reason_codes.append("high_burn_rate")

            # 6. Critical lead time
            if lead_time >= 2 and physical_stock <= (burn_rate * lead_time):
                score += 20
                reason_codes.append("lead_time_critical")

            # 7. Cold start
            if is_cold_start:
                score += 10
                reason_codes.append("cold_start")

            # Only include SKUs that meet risk threshold (score >= 30)
            if score >= 30:
                sku_context = SKUContext(
                    sku_id=sku.sku_id,
                    sku_name=sku.sku_name,
                    category=sku.category,
                    physical_stock=physical_stock,
                    threshold=threshold,
                    average_daily_burn_rate=burn_rate,
                    lead_time_days=lead_time,
                    moq=sku.moq,
                    packaging_multiple=sku.packaging_multiple,
                    base_unit=sku.base_unit,
                    open_pr_qty=stock_info.get("open_pr_qty", 0),
                    is_cold_start=is_cold_start
                )

                # Context Aggregation
                weather_ctx = self.weather.get_weather_for_zone(store.zone)
                calendar_ctx = self.calendar_promo.get_calendar_context()
                ext_ctx = ExternalContext(
                    weather=weather_ctx,
                    calendar=calendar_ctx,
                    promo=promo_context
                )

                # Fetch recent feedback if any
                recent_feedbacks = self.db.list_recent_feedback(store.store_id, sku.sku_id, limit=1)
                feedback_str = recent_feedbacks[0].reason if recent_feedbacks else None

                agg_context = AggregationContext(
                    store=store,
                    sku=sku_context,
                    external_context=ext_ctx,
                    recent_feedback=feedback_str
                )

                priority_list.append(PrioritySKU(
                    sku_id=sku.sku_id,
                    sku_name=sku.sku_name,
                    priority_score=min(100, score),
                    reason_codes=reason_codes,
                    context=agg_context
                ))

        # Sort descending by priority score
        priority_list.sort(key=lambda x: x.priority_score, reverse=True)
        return priority_list

    def process_store_evaluation(
        self,
        store: StoreProfile,
        skus: List[SKUProfile],
        stock_levels: Dict[str, Dict[str, Any]],
        run_id: Optional[str] = None
    ) -> List[AuditLogRecord]:
        """
        Execute full replenishment evaluation for a store:
        Prioritization -> AI Reasoning -> MOQ Adjust -> Telegram Card -> State & Audit Log
        """
        current_run_id = run_id or f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
        now_dt = datetime.now(timezone.utc)
        created_at_str = now_dt.isoformat()
        expires_at_str = (now_dt + timedelta(hours=APPROVAL_TIMEOUT_HOURS)).isoformat()

        priority_skus = self.prioritize_skus(store, skus, stock_levels)
        processed_logs = []

        for p_sku in priority_skus:
            context = p_sku.context
            if not context:
                continue

            request_id = f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            # 1. AI Reasoning via Bedrock
            ai_recommendation = self.bedrock.generate_recommendation(context)

            # 2. MOQ and Packaging Multiple Adjustment
            final_qty, moq_app, pack_app, adj_note = MoqPackagingService.adjust_quantity(
                raw_qty=ai_recommendation.recommended_qty,
                moq=context.sku.moq,
                packaging_multiple=context.sku.packaging_multiple,
                category=context.sku.category,
                risk_level=ai_recommendation.risk_level,
                area_type=store.area_type,
                weather_condition=context.external_context.weather.condition
            )

            # Update recommendation flags
            ai_recommendation.moq_applied = moq_app
            ai_recommendation.packaging_multiple_applied = pack_app

            # 3. Send Telegram Recommendation Card
            telegram_msg = self.telegram.send_recommendation_card(
                chat_id=store.telegram_chat_id,
                context=context,
                recommendation=ai_recommendation,
                final_qty=final_qty,
                request_id=request_id
            )

            # 4. Save Telegram State in DynamoDB
            telegram_state = TelegramStateRecord(
                PK=f"REQ#{request_id}",
                SK="STATE",
                request_id=request_id,
                run_id=current_run_id,
                store_id=store.store_id,
                sku_id=context.sku.sku_id,
                recommended_qty=final_qty,
                status="PENDING_APPROVAL",
                telegram_chat_id=store.telegram_chat_id,
                telegram_message_id=telegram_msg.get("message_id"),
                created_at=created_at_str,
                expires_at=expires_at_str
            )
            self.db.put_telegram_state(telegram_state)

            # 5. Record Audit Log
            audit_record = AuditLogRecord(
                request_id=request_id,
                run_id=current_run_id,
                store_id=store.store_id,
                store_name=store.store_name,
                area_type=store.area_type,
                sku_id=context.sku.sku_id,
                sku_name=context.sku.sku_name,
                category=context.sku.category,
                physical_stock=context.sku.physical_stock,
                threshold=context.sku.threshold,
                average_daily_burn_rate=context.sku.average_daily_burn_rate,
                lead_time_days=context.sku.lead_time_days,
                moq=context.sku.moq,
                packaging_multiple=context.sku.packaging_multiple,
                weather_condition=context.external_context.weather.condition,
                weather_source=context.external_context.weather.source,
                weather_stale=context.external_context.weather.is_stale,
                calendar_day=context.external_context.calendar.day_type,
                is_public_holiday=context.external_context.calendar.is_public_holiday,
                is_payday=context.external_context.calendar.is_payday,
                promo_active=context.external_context.promo.is_active,
                promo_type=context.external_context.promo.promo_type,
                prompt_version=ai_recommendation.prompt_version,
                model=self.bedrock.model_id,
                ai_recommended_qty=ai_recommendation.recommended_qty,
                normal_qty=ai_recommendation.normal_qty,
                adjusted_qty_before_moq=ai_recommendation.adjusted_qty_before_moq,
                final_recommended_qty=final_qty,
                moq_applied=moq_app,
                packaging_multiple_applied=pack_app,
                confidence_score=ai_recommendation.confidence_score,
                risk_level=ai_recommendation.risk_level,
                reasoning_narrative=ai_recommendation.reasoning_narrative,
                key_factors=ai_recommendation.key_factors,
                warnings=ai_recommendation.warnings,
                sap_pr_status="PENDING",
                created_at=created_at_str
            )
            self.db.put_audit_log(audit_record)
            processed_logs.append(audit_record)

        return processed_logs
