"""Scheduled Evaluation Lambda Handler.

Triggered by EventBridge at 05:00 WIB and 14:00 WIB.
Scans stores, prioritizes SKUs, runs Bedrock AI reasoning, and dispatches Telegram cards.
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from ..config import logger
from ..models.schema import StoreProfile, SKUProfile
from ..services.dynamodb_service import DynamoDBService
from ..services.weather_service import WeatherService
from ..services.calendar_promo_service import CalendarPromoService
from ..services.bedrock_service import BedrockReasoningService
from ..services.telegram_service import TelegramService
from ..services.orchestrator_service import OrchestratorService

# Default Pilot Stores & SKUs matching PRD Section 7, 11, 19, 21.5
DEFAULT_PILOT_STORES = [
    StoreProfile(
        store_id="STR-001",
        store_name="Cabang Sudirman",
        area_type="Perkantoran",
        zone="JAKARTA_PUSAT",
        sap_plant="1000",
        storage_location="STR-001",
        telegram_chat_id="chat_budi_001",
        active=True
    ),
    StoreProfile(
        store_id="STR-002",
        store_name="Cabang Kemang",
        area_type="Perumahan",
        zone="JAKARTA_SELATAN",
        sap_plant="1000",
        storage_location="STR-002",
        telegram_chat_id="chat_siti_002",
        active=True
    ),
    StoreProfile(
        store_id="STR-003",
        store_name="Cabang Dago",
        area_type="Kampus",
        zone="BANDUNG_KOTA",
        sap_plant="2000",
        storage_location="STR-003",
        telegram_chat_id="chat_andi_003",
        active=True
    )
]

DEFAULT_PILOT_SKUS = [
    SKUProfile(
        sku_id="SKU-10023",
        sku_name="Roti Manis Cokelat 100g",
        category="Perishable",
        weather_sensitive=True,
        moq=12,
        packaging_multiple=12,
        base_unit="PCS",
        default_lead_time_days=2,
        vendor_id="VEN-009",
        price_idr=12500.0
    ),
    SKUProfile(
        sku_id="SKU-10045",
        sku_name="Minuman Isotonik 500ml",
        category="Non-Perishable",
        weather_sensitive=True,
        moq=24,
        packaging_multiple=24,
        base_unit="PCS",
        default_lead_time_days=2,
        vendor_id="VEN-014",
        price_idr=8500.0
    ),
    SKUProfile(
        sku_id="SKU-10088",
        sku_name="Sabun Cuci Piring 750ml",
        category="Non-Perishable",
        weather_sensitive=False,
        moq=12,
        packaging_multiple=6,
        base_unit="PCS",
        default_lead_time_days=3,
        vendor_id="VEN-031",
        price_idr=16000.0
    ),
    SKUProfile(
        sku_id="SKU-10099",
        sku_name="Susu Pasteurisasi Cokelat 200ml",
        category="Perishable",
        weather_sensitive=True,
        moq=10,
        packaging_multiple=10,
        base_unit="PCS",
        default_lead_time_days=1,
        vendor_id="VEN-004",
        price_idr=11000.0
    )
]

DEFAULT_STOCK_LEVELS = {
    "STR-001": {
        "SKU-10023": {"physical_stock": 12, "threshold": 20, "average_daily_burn_rate": 25.0, "lead_time_days": 2, "open_pr_qty": 0},
        "SKU-10045": {"physical_stock": 18, "threshold": 30, "average_daily_burn_rate": 20.0, "lead_time_days": 2, "open_pr_qty": 0},
        "SKU-10088": {"physical_stock": 35, "threshold": 15, "average_daily_burn_rate": 5.0, "lead_time_days": 3, "open_pr_qty": 0},
        "SKU-10099": {"physical_stock": 6, "threshold": 15, "average_daily_burn_rate": 12.0, "lead_time_days": 1, "open_pr_qty": 0},
    },
    "STR-002": {
        "SKU-10023": {"physical_stock": 15, "threshold": 20, "average_daily_burn_rate": 18.0, "lead_time_days": 2, "open_pr_qty": 0},
        "SKU-10045": {"physical_stock": 8, "threshold": 25, "average_daily_burn_rate": 22.0, "lead_time_days": 2, "open_pr_qty": 0},
        "SKU-10088": {"physical_stock": 10, "threshold": 20, "average_daily_burn_rate": 14.0, "lead_time_days": 3, "open_pr_qty": 0},
        "SKU-10099": {"physical_stock": 14, "threshold": 15, "average_daily_burn_rate": 8.0, "lead_time_days": 1, "open_pr_qty": 0},
    },
    "STR-003": {
        "SKU-10023": {"physical_stock": 25, "threshold": 20, "average_daily_burn_rate": 15.0, "lead_time_days": 2, "open_pr_qty": 0},
        "SKU-10045": {"physical_stock": 12, "threshold": 30, "average_daily_burn_rate": 28.0, "lead_time_days": 2, "open_pr_qty": 0},
        "SKU-10088": {"physical_stock": 8, "threshold": 15, "average_daily_burn_rate": 6.0, "lead_time_days": 3, "open_pr_qty": 0},
        "SKU-10099": {"physical_stock": 4, "threshold": 12, "average_daily_burn_rate": 10.0, "lead_time_days": 1, "open_pr_qty": 0},
    }
}


def seed_database_if_empty(db: DynamoDBService):
    """Seed initial store and SKU metadata if not present."""
    if not db.list_all_stores():
        for s in DEFAULT_PILOT_STORES:
            db.put_store(s)
    if not db.list_all_skus():
        for k in DEFAULT_PILOT_SKUS:
            db.put_sku(k)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Execute scheduled replenishment evaluation."""
    logger.info("Starting AutoReplenish Scheduled Stock Evaluation")
    
    db_service = DynamoDBService()
    weather_service = WeatherService(db_service)
    calendar_promo_service = CalendarPromoService()
    bedrock_service = BedrockReasoningService()
    telegram_service = TelegramService()

    seed_database_if_empty(db_service)

    orchestrator = OrchestratorService(
        db_service=db_service,
        weather_service=weather_service,
        calendar_promo_service=calendar_promo_service,
        bedrock_service=bedrock_service,
        telegram_service=telegram_service
    )

    run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    stores = db_service.list_all_stores()
    skus = db_service.list_all_skus()

    total_evaluated_skus = 0
    total_recommendations = 0
    generated_logs = []

    for store in stores:
        if not store.active:
            continue
        store_stock = DEFAULT_STOCK_LEVELS.get(store.store_id, {})
        logs = orchestrator.process_store_evaluation(
            store=store,
            skus=skus,
            stock_levels=store_stock,
            run_id=run_id
        )
        total_recommendations += len(logs)
        total_evaluated_skus += len(skus)
        generated_logs.extend([l.to_dict() for l in logs])

    logger.info(f"Evaluation finished for run {run_id}. Processed {total_recommendations} recommendations across {len(stores)} stores.")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "run_id": run_id,
            "stores_count": len(stores),
            "total_evaluated_skus": total_evaluated_skus,
            "total_recommendations_dispatched": total_recommendations,
            "recommendations": generated_logs
        })
    }
