"""Test fixtures and mocks for AutoReplenish.ai.

Every test runs against a moto-emulated DynamoDB table (real boto3 code paths,
no AWS account required) plus in-process doubles for Bedrock, OpenWeatherMap,
Telegram, and the SAP gateway. mocks declared in infra/secrets.tf are modelled
by SecretsManager double services so the dual-mode SAP logic is exercised
end to end.
"""

import os
import sys
import contextlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import boto3
import pytest
from moto import mock_aws

# Ensure backend package is importable
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
    SapPRPayload,
    SapPRItem,
)
from src.services.dynamodb_service import DynamoDBService
from src.services.weather_service import WeatherService
from src.services.calendar_promo_service import CalendarPromoService
from src.services.bedrock_service import BedrockReasoningService
from src.services.telegram_service import TelegramService
from src.services.orchestrator_service import OrchestratorService

TEST_TABLE_NAME = "autoreplenish-main-test"
TEST_REGION = "ap-southeast-1"


# -------------------------------------------------------------
# Moto table factory (real boto3 calls, emulated locally)
# -------------------------------------------------------------
@contextlib.contextmanager
def moto_dynamo_table(table_name: str = TEST_TABLE_NAME):
    """Create a DynamoDB table with the exact PK/SK + GSI1 + GSI2 schema
    defined in infra/dynamodb.tf, and yield a boto3 Table resource."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=TEST_REGION)
        table = ddb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def table():
    with moto_dynamo_table() as t:
        yield t


@pytest.fixture
def db(table):
    """DynamoDBService wired to the emulated table via DI."""
    return DynamoDBService(table_name=TEST_TABLE_NAME, client=table)


@pytest.fixture
def seeded_db(db):
    """DB pre-populated with the generic multi-store seed master data."""
    from src.data.master_data_loader import load_seed_skus, load_seed_stores
    for store in load_seed_stores():
        db.put_store(store)
    for sku in load_seed_skus():
        db.put_sku(sku)
    return db


# -------------------------------------------------------------
# Master data (Toko Almadina Sembako, Wirosari - Grobogan)
# -------------------------------------------------------------
def almadina_store(telegram_chat_id: str = "1181431005") -> StoreProfile:
    return StoreProfile(
        store_id="STR-ALMADINA-001",
        store_name="Toko Almadina Sembako",
        area_type="Sub-Urban / Sentra Pemukiman Kecamatan",
        zone="GROBOGAN_WIROSARI",
        address="W36X+286, Beru Kulon, Kalirejo, Kec. Wirosari, Grobogan, Jawa Tengah 58192",
        sap_plant="1000",
        storage_location="STR-ALMADINA-001",
        telegram_chat_id=telegram_chat_id,
        active=True,
    )


def sku_perishable_fragile() -> SKUProfile:
    """Telur Ayam Ras Segar 1kg — perishable, fragile, high burn rate."""
    return SKUProfile(
        sku_id="SKU-ALM-003",
        sku_name="Telur Ayam Ras Segar 1kg",
        category="Perishable",
        weather_sensitive=True,
        moq=10,
        packaging_multiple=10,
        base_unit="KG",
        default_lead_time_days=1,
        vendor_id="VEN-TLR-004",
        price_idr=28500.0,
        shelf_life_days=14,
        is_fragile=True,
    )


def sku_short_shelf_life() -> SKUProfile:
    """Roti Basah Tradisional / Kue Pangan 100g — 3-day shelf life."""
    return SKUProfile(
        sku_id="SKU-ALM-004",
        sku_name="Roti Basah Tradisional / Kue Pangan 100g",
        category="Perishable",
        weather_sensitive=True,
        moq=12,
        packaging_multiple=12,
        base_unit="PCS",
        default_lead_time_days=1,
        vendor_id="VEN-BKR-021",
        price_idr=3500.0,
        shelf_life_days=3,
        is_fragile=True,
    )


def sku_non_perishable() -> SKUProfile:
    """Beras Medium Premium 5kg — non-perishable staple."""
    return SKUProfile(
        sku_id="SKU-ALM-001",
        sku_name="Beras Medium Premium 5kg",
        category="Non-Perishable",
        weather_sensitive=False,
        moq=5,
        packaging_multiple=5,
        base_unit="KARUNG",
        default_lead_time_days=3,
        vendor_id="VEN-PMD-001",
        price_idr=68000.0,
        shelf_life_days=365,
        is_fragile=False,
    )


def build_context(sku: SKUProfile, store: Optional[StoreProfile] = None) -> AggregationContext:
    """Build a full AggregationContext for reasoning tests."""
    store = store or almadina_store()
    return AggregationContext(
        store=store,
        sku=SKUContext(
            sku_id=sku.sku_id,
            sku_name=sku.sku_name,
            category=sku.category,
            physical_stock=4,
            threshold=12,
            average_daily_burn_rate=8.0,
            lead_time_days=sku.default_lead_time_days,
            moq=sku.moq,
            packaging_multiple=sku.packaging_multiple,
            base_unit=sku.base_unit,
            open_pr_qty=0,
            is_cold_start=False,
            shelf_life_days=sku.shelf_life_days,
            is_fragile=sku.is_fragile,
        ),
        external_context=ExternalContext(
            weather=WeatherContext(
                condition="Hujan Ringan",
                temperature_c=28.0,
                rain_probability=0.55,
                forecast="Berawan dengan hujan lokal",
                source="OpenWeatherMap",
            ),
            calendar=CalendarContext(day_type="Weekend", day_of_week="Saturday"),
            promo=PromoContext(is_active=False),
        ),
    )


# -------------------------------------------------------------
# Fake Bedrock client
# -------------------------------------------------------------
class FakeBedrockBody:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class FakeBedrockClient:
    """Records invocation payloads and returns canned Claude responses."""

    def __init__(self, response_text: Optional[str] = None, raise_exc: Optional[Exception] = None):
        self.response_text = response_text or _valid_bedrock_json()
        self.raise_exc = raise_exc
        self.invocations: List[Dict[str, Any]] = []

    def invoke_model(self, modelId, body, contentType, accept):
        import json as _json

        self.invocations.append({
            "modelId": modelId,
            "body": _json.loads(body),
            "contentType": contentType,
            "accept": accept,
        })
        if self.raise_exc:
            raise self.raise_exc
        return {
            "body": FakeBedrockBody(
                _json.dumps({"content": [{"type": "text", "text": self.response_text}]}).encode()
            )
        }


def _valid_bedrock_json() -> str:
    import json as _json

    return _json.dumps({
        "recommended_qty": 24,
        "normal_qty": 60,
        "adjusted_qty_before_moq": 24,
        "moq_applied": True,
        "packaging_multiple_applied": True,
        "confidence_score": 0.91,
        "risk_level": "medium",
        "reasoning_narrative": "Stok telur 4 kg di bawah threshold 12 kg dengan burn rate 8 kg/hari.",
        "key_factors": ["below_threshold", "fragile"],
        "warnings": ["Barang mudah pecah, gunakan tray"],
    })


def create_test_orchestrator(db, telegram_service=None, bedrock_service=None):
    """Wire an OrchestratorService over a given DB (defaults: moto table)."""
    weather = WeatherService(db, api_key="test-owm-key")
    return OrchestratorService(
        db_service=db,
        weather_service=weather,
        calendar_promo_service=CalendarPromoService(),
        bedrock_service=bedrock_service or BedrockReasoningService(bedrock_client=FakeBedrockClient()),
        telegram_service=telegram_service or TelegramService(bot_token="test-token", http_client=FakeHTTPClient()),
    )


# -------------------------------------------------------------
# Fake HTTP client (Telegram + OpenWeatherMap)
# -------------------------------------------------------------
class FakeHTTPResponse:
    def __init__(self, status_code: int = 200, json_data: Any = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self.content = b"{}"
        self.headers: Dict[str, str] = {}
        self.records: List[Dict[str, Any]] = []

    def json(self):
        return self._json


class FakeHTTPClient:
    """Requests-like double that records calls and replays queued responses."""

    def __init__(self, responses: Optional[List[FakeHTTPResponse]] = None):
        self.responses = responses or []
        self.calls: List[Dict[str, Any]] = []
        self.default_response: Optional[FakeHTTPResponse] = None

    def _next(self) -> FakeHTTPResponse:
        if self.responses:
            return self.responses.pop(0)
        if self.default_response is not None:
            return self.default_response
        return FakeHTTPResponse(200, {"result": {"message_id": 4242, "id": 1}})

    def get(self, url, params=None, headers=None, timeout=None, **kwargs):
        response = self._next()
        self.calls.append({"method": "GET", "url": url, "params": params, "headers": headers})
        return response

    def post(self, url, json=None, data=None, headers=None, timeout=None, **kwargs):
        response = self._next()
        self.calls.append({
            "method": "POST",
            "url": url,
            "json": json,
            "data": data,
            "headers": headers,
        })
        return response


def telegram_ok_response(message_id: int = 4242) -> FakeHTTPResponse:
    return FakeHTTPResponse(200, {"ok": True, "result": {"message_id": message_id}})


# -------------------------------------------------------------
# Secret doubles
# -------------------------------------------------------------
class FakeSecretManager:
    """Stands in for AWS Secrets Manager so credentials stay out of tests."""

    def __init__(self, secrets: Optional[Dict[str, Dict[str, Any]]] = None):
        self.secrets = secrets or {}

    def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        return self.secrets.get(secret_name, {})

    def get_weather_api_key(self, secret_name: str) -> str:
        return str(self.secrets.get(secret_name, {}).get("api_key", ""))

    def get_telegram_bot_token(self, secret_name: str) -> str:
        return str(self.secrets.get(secret_name, {}).get("bot_token", ""))

    def get_telegram_chat_id(self, secret_name: str) -> str:
        return str(self.secrets.get(secret_name, {}).get("chat_id", ""))

    def get_telegram_webhook_secret(self, secret_name: str) -> str:
        return str(self.secrets.get(secret_name, {}).get("webhook_secret", ""))

    def get_sap_credentials(self, secret_name: str) -> Dict[str, Any]:
        base = {
            "client_id": "",
            "client_secret": "",
            "token_url": "",
            "odata_base_url": "",
            "sap_client": "100",
        }
        base.update(self.secrets.get(secret_name, {}))
        return base


# -------------------------------------------------------------
# SAP payload helpers
# -------------------------------------------------------------
def make_pr_payload(quantity: int = 24, sku_id: str = "SKU-ALM-003") -> SapPRPayload:
    return SapPRPayload(
        PurchaseRequisitionType="NB",
        PurchaseRequisitionItems=[
            SapPRItem(
                Material=sku_id,
                Plant="1000",
                StoreLocation="STR-ALMADINA-001",
                RequestedQuantity=quantity,
                BaseUnit="KG",
                DeliveryDate=(datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d"),
                ShortText="AutoReplenish.ai - Telur Ayam Ras Segar 1kg",
            )
        ],
    )


# -------------------------------------------------------------
# Weather payload (OpenWeatherMap shape)
# -------------------------------------------------------------
def owm_payload(
    temp: float = 28.5,
    description: str = "light rain",
    rain_1h: Optional[float] = None,
    humidity: int = 82,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "coord": {"lon": 111.1687, "lat": -7.0864},
        "main": {"temp": temp, "humidity": humidity, "pressure": 1009},
        "weather": [{"id": 500, "main": "Rain", "description": description}],
        "wind": {"speed": 3.1},
        "clouds": {"all": 75},
        "dt": 1700000000,
    }
    if rain_1h is not None:
        payload["rain"] = {"1h": rain_1h}
    return payload
