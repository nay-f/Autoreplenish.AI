"""Scheduled Evaluation Lambda Handler.

Triggered by EventBridge at 05:00 WIB and 14:00 WIB (see infra/eventbridge.tf).
Scans stores, prioritizes SKUs, runs Bedrock AI reasoning, and dispatches
Telegram cards.

Master data (stores, SKUs, opening stock) is generic and multi-store: it lives in
backend/src/data/seed_stores.json and seed_skus.json and is read through
``master_data_loader``. It is seeded into the real DynamoDB table only when the
store/SKU collections are empty, so a production deployment can override it
with genuine SAP/OData master data.
"""

import json
from typing import Any, Dict, List

from datetime import datetime, timezone

from ..config import logger, TELEGRAM_SECRET_NAME
from ..data.master_data_loader import load_seed_skus, load_seed_stores
from ..services.dynamodb_service import DynamoDBService
from ..services.weather_service import WeatherService
from ..services.calendar_promo_service import CalendarPromoService
from ..services.bedrock_service import BedrockReasoningService
from ..services.telegram_service import TelegramService
from ..services.secrets_service import SecretManagerService
from ..services.orchestrator_service import OrchestratorService


def seed_database_if_empty(db: DynamoDBService) -> Dict[str, Any]:
    """Seed store / SKU master data (from the JSON fixtures) only when the collections are empty."""
    seeded = {"stores": 0, "skus": 0}
    if not db.list_all_stores():
        for store in load_seed_stores():
            db.put_store(store)
            seeded["stores"] += 1
    if not db.list_all_skus():
        for sku in load_seed_skus():
            db.put_sku(sku)
            seeded["skus"] += 1
    if seeded["stores"] or seeded["skus"]:
        logger.info(f"Seeded master data: {seeded}")
    return seeded


def _apply_pilot_chat_id(db: DynamoDBService, secret_service: SecretManagerService) -> None:
    """Populate telegram_chat_id for stores that have none configured yet."""
    pilot_chat_id = secret_service.get_telegram_chat_id(TELEGRAM_SECRET_NAME)
    if not pilot_chat_id:
        logger.warning("No Telegram chat_id configured; cards cannot be delivered")
        return
    for store in db.list_all_stores():
        if store.telegram_chat_id != pilot_chat_id:
            store.telegram_chat_id = pilot_chat_id
            db.put_store(store)
            logger.info(f"Bound store {store.store_id} to pilot Telegram chat")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Execute the scheduled replenishment evaluation."""
    trigger = (event or {}).get("trigger_source", "MANUAL")
    logger.info(f"Starting AutoReplenish Scheduled Stock Evaluation (trigger={trigger})")

    secret_service = SecretManagerService()
    db_service = DynamoDBService()
    weather_service = WeatherService(db_service, secret_service=secret_service)
    calendar_promo_service = CalendarPromoService()
    bedrock_service = BedrockReasoningService()
    telegram_service = TelegramService(secret_service=secret_service)

    seed_database_if_empty(db_service)
    _apply_pilot_chat_id(db_service, secret_service)

    orchestrator = OrchestratorService(
        db_service=db_service,
        weather_service=weather_service,
        calendar_promo_service=calendar_promo_service,
        bedrock_service=bedrock_service,
        telegram_service=telegram_service,
    )

    run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    stores = orchestrator.get_stores()
    skus = orchestrator.get_skus()

    generated_logs: List[Dict[str, Any]] = []
    fallback_count = 0
    weather_api_calls = 0

    for store in stores:
        if not store.active:
            continue
        store_stock = orchestrator.get_opening_stock(store.store_id)
        logs = orchestrator.process_store_evaluation(
            store=store,
            skus=skus,
            stock_levels=store_stock,
            run_id=run_id,
        )
        generated_logs.extend([l.to_dict() for l in logs])
        fallback_count += sum(1 for l in logs if l.is_fallback)
        weather_api_calls += weather_service.api_calls_this_invocation

    logger.info(
        f"Evaluation finished for run {run_id}: {len(generated_logs)} recommendation(s) "
        f"across {len(stores)} store(s); {fallback_count} used the rule-based fallback; "
        f"{weather_api_calls} external weather API call(s)."
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "run_id": run_id,
            "trigger_source": trigger,
            "stores_count": len(stores),
            "total_skus_catalogued": len(skus),
            "total_recommendations_dispatched": len(generated_logs),
            "rule_based_fallback_count": fallback_count,
            "weather_api_calls": weather_api_calls,
            "recommendations": generated_logs,
        }, default=str),
    }
