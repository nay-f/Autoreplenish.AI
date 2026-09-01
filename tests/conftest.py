"""Test Fixtures and Mocks for AutoReplenish.ai Test Suite."""

import sys
import os

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from src.models.schema import (
    StoreProfile,
    SKUProfile,
    WeatherContext,
    CalendarContext,
    PromoContext,
    ExternalContext,
    SKUContext,
    AggregationContext,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.weather_service import WeatherService
from src.services.calendar_promo_service import CalendarPromoService
from src.services.bedrock_service import BedrockReasoningService
from src.services.telegram_service import TelegramService
from src.services.sap_service import SapIntegrationService
from src.services.orchestrator_service import OrchestratorService

def get_test_store() -> StoreProfile:
    return StoreProfile(
        store_id="STR-001",
        store_name="Cabang Sudirman",
        area_type="Perkantoran",
        zone="JAKARTA_PUSAT",
        sap_plant="1000",
        storage_location="STR-001",
        telegram_chat_id="chat_budi_001",
        active=True
    )

def get_test_sku_perishable() -> SKUProfile:
    return SKUProfile(
        sku_id="SKU-10023",
        sku_name="Roti Manis Cokelat 100g",
        category="Perishable",
        weather_sensitive=True,
        moq=12,
        packaging_multiple=12,
        base_unit="PCS",
        default_lead_time_days=2,
        vendor_id="VEN-009"
    )

def get_test_sku_non_perishable() -> SKUProfile:
    return SKUProfile(
        sku_id="SKU-10045",
        sku_name="Minuman Isotonik 500ml",
        category="Non-Perishable",
        weather_sensitive=True,
        moq=24,
        packaging_multiple=24,
        base_unit="PCS",
        default_lead_time_days=2,
        vendor_id="VEN-014"
    )

def create_test_orchestrator():
    db = DynamoDBService()
    weather = WeatherService(db)
    calendar_promo = CalendarPromoService()
    bedrock = BedrockReasoningService()
    telegram = TelegramService()
    sap = SapIntegrationService()
    orchestrator = OrchestratorService(db, weather, calendar_promo, bedrock, telegram)
    return {
        "db": db,
        "weather": weather,
        "calendar_promo": calendar_promo,
        "bedrock": bedrock,
        "telegram": telegram,
        "sap": sap,
        "orchestrator": orchestrator
    }
