"""Data Models & Schemas for AutoReplenish.ai.

Defines all structures for Store, SKU, External Signals, AI Reasoning,
Telegram State Machine, SAP OData PR payload, SAP Transaction Ledger, and Audit Logging.

All entity ``to_dict()`` methods also emit the Global Secondary Index attributes
(GSI1PK/GSI1SK, GSI2PK/GSI2SK) required by the real DynamoDB single-table layout
defined in ``infra/dynamodb.tf``.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any

# -------------------------------------------------------------
# DynamoDB Single-Table Access Pattern (PRD Section 13)
# -------------------------------------------------------------
# Entity          | PK                         | SK                            | GSI1PK  | GSI1SK
# ----------------|----------------------------|-------------------------------|---------|---------------------------------
# StoreProfile    | STORE#{store_id}           | PROFILE                       | STORE   | {store_id}
# SKUProfile      | SKU#{sku_id}               | PROFILE                       | SKU     | {sku_id}
# WeatherCache    | ZONE#{zone_id}             | WEATHER#{timestamp}           | -       | -
# TelegramState   | REQ#{request_id}           | STATE                         | -       | -
# AuditLog        | AUDIT#{store_id}           | TS#{created}#SKU#{sku_id}     | AUDIT   | {created}#{request_id}
# FeedbackLog     | FEEDBACK#{store}#{sku}     | TS#{created}                  | FEEDBACK| {created}#{store}#{sku}
# SapTransaction  | SAPTRANS#{request_id}      | TRANSACTION                   | SAPTRANS| {created}#{request_id}
#
# GSI2 (sparse): cross-partition business-key lookups
#   AuditLog       -> GSI2PK = AUDIT#{request_id}
#   SapTransaction -> GSI2PK = SAPPR#{sap_pr_id}
# -------------------------------------------------------------


# -------------------------------------------------------------
# Store & SKU Metadata and Operational Configurations
# -------------------------------------------------------------
@dataclass
class IngestionConfig:
    mode: str = "SAP"  # "POS" or "SAP"
    pos_connector_type: str = "REST Webhook"  # REST Webhook, Direct DB Sync, CSV/JSON Auto-Import
    pos_sync_schedule: str = "21:00"  # default: 21:00 / Saat Tutup Toko
    webhook_secret: str = "sec_pos_live_9f82a1"
    sap_odata_url: str = "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV"
    sap_token_url: str = ""
    sap_client_id: str = ""
    sap_client_secret: str = ""
    sap_plant: str = "1000"
    sap_storage_location: str = "WH-01"
    sap_purchasing_org: str = "1000"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HITLConfig:
    telegram_chat_id: str = ""
    timeout_tolerance_hours: int = 4
    enable_auto_reminder: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcurementRule:
    sku_id: str
    sku_name: str = ""
    category: str = "FMCG"
    safety_stock_threshold: int = 10
    supplier_lead_time_days: int = 2
    delivery_window: List[str] = field(default_factory=lambda: ["Senin", "Rabu", "Jumat"])
    moq: int = 1
    packaging_multiple: int = 1
    is_perishable: bool = False
    shelf_life_days: int = 365

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromoEvent:
    promo_id: str
    promo_name: str
    promo_type: str = "JSM / Weekend"  # Diskon Persen, JSM / Weekend, Buy 1 Get 1
    start_date: str = ""
    end_date: str = ""
    target_sku_ids: List[str] = field(default_factory=list)
    multiplier_factor: float = 1.3

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocalCommunityEvent:
    event_id: str
    event_name: str
    event_date: str
    impact_multiplier: float = 1.2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StoreProfile:
    store_id: str
    store_name: str
    area_type: str = "Umum"  # e.g. Komersial / Perkantoran, Residensial / Pemukiman, Pasar / Sub-Urban
    zone: str = "DEFAULT"
    address: str = ""
    sap_plant: str = "1000"
    storage_location: str = ""
    telegram_chat_id: str = ""
    active: bool = True
    # Store geolocation (WGS84) used for per-store weather lookups.
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_zone: str = ""
    ingestion_config: IngestionConfig = field(default_factory=IngestionConfig)
    hitl_config: HITLConfig = field(default_factory=HITLConfig)
    procurement_rules: Dict[str, ProcurementRule] = field(default_factory=dict)
    promos: List[PromoEvent] = field(default_factory=list)
    local_events: List[LocalCommunityEvent] = field(default_factory=list)
    PK: str = ""
    SK: str = "PROFILE"

    def __post_init__(self):
        if isinstance(self.ingestion_config, dict):
            self.ingestion_config = IngestionConfig(**self.ingestion_config)
        if isinstance(self.hitl_config, dict):
            self.hitl_config = HITLConfig(**self.hitl_config)
        if isinstance(self.procurement_rules, dict):
            rules = {}
            for k, v in self.procurement_rules.items():
                rules[k] = ProcurementRule(**v) if isinstance(v, dict) else v
            self.procurement_rules = rules
        if isinstance(self.promos, list):
            self.promos = [PromoEvent(**p) if isinstance(p, dict) else p for p in self.promos]
        if isinstance(self.local_events, list):
            self.local_events = [LocalCommunityEvent(**e) if isinstance(e, dict) else e for e in self.local_events]

        if not self.delivery_zone and self.zone:
            self.delivery_zone = self.zone
        if not self.telegram_chat_id and self.hitl_config and self.hitl_config.telegram_chat_id:
            self.telegram_chat_id = self.hitl_config.telegram_chat_id
        elif self.telegram_chat_id and self.hitl_config and not self.hitl_config.telegram_chat_id:
            self.hitl_config.telegram_chat_id = self.telegram_chat_id

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"STORE#{self.store_id}"
        d["SK"] = "PROFILE"
        d["GSI1PK"] = "STORE"
        d["GSI1SK"] = self.store_id
        return d


# PRD Section 13.3 refers to the store master record as "StoreMetadata".
StoreMetadata = StoreProfile


@dataclass
class SKUProfile:
    sku_id: str
    sku_name: str
    category: str = "Non-Perishable"  # Perishable or Non-Perishable
    weather_sensitive: bool = False
    moq: int = 1
    packaging_multiple: int = 1
    base_unit: str = "PCS"
    default_lead_time_days: int = 2
    vendor_id: str = "VEN-001"
    price_idr: float = 15000.0
    # Physical/commercial attributes used for conservative replenishment decisions.
    shelf_life_days: int = 365          # Perishability depth (e.g. 3 days for wet bakery / traditional cake)
    is_fragile: bool = False            # Fragile goods (eggs) get spoilage/breakage penalties
    PK: str = ""
    SK: str = "PROFILE"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"SKU#{self.sku_id}"
        d["SK"] = "PROFILE"
        d["GSI1PK"] = "SKU"
        d["GSI1SK"] = self.sku_id
        return d


# -------------------------------------------------------------
# Context Aggregation Schemas
# -------------------------------------------------------------
@dataclass
class WeatherContext:
    condition: str = "Cerah Berawan"
    temperature_c: float = 30.0
    rain_probability: float = 0.2
    forecast: str = "Cerah berawan sepanjang hari"
    source: str = "OpenWeatherMap"
    is_stale: bool = False
    is_unavailable: bool = False
    fetched_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalendarContext:
    day_type: str = "Weekday"  # Weekday or Weekend
    day_of_week: str = "Monday"
    is_public_holiday: bool = False
    holiday_name: Optional[str] = None
    is_payday: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromoContext:
    is_active: bool = False
    promo_type: Optional[str] = None  # e.g., "JSM", "Buy 1 Get 1", "Diskon 20%"
    promo_name: Optional[str] = None
    multiplier_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExternalContext:
    weather: WeatherContext
    calendar: CalendarContext
    promo: PromoContext

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weather": self.weather.to_dict(),
            "calendar": self.calendar.to_dict(),
            "promo": self.promo.to_dict(),
        }


@dataclass
class SKUContext:
    sku_id: str
    sku_name: str
    category: str
    physical_stock: int
    threshold: int
    average_daily_burn_rate: float
    lead_time_days: int
    moq: int = 1
    packaging_multiple: int = 1
    base_unit: str = "PCS"
    open_pr_qty: int = 0
    is_cold_start: bool = False
    shelf_life_days: int = 365
    is_fragile: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AggregationContext:
    store: StoreProfile
    sku: SKUContext
    external_context: ExternalContext
    recent_feedback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store": self.store.to_dict(),
            "sku": self.sku.to_dict(),
            "external_context": self.external_context.to_dict(),
            "recent_feedback": self.recent_feedback,
        }


# -------------------------------------------------------------
# Prioritization Models
# -------------------------------------------------------------
@dataclass
class PrioritySKU:
    sku_id: str
    sku_name: str
    priority_score: int
    reason_codes: List[str]
    context: Optional[AggregationContext] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "sku_id": self.sku_id,
            "sku_name": self.sku_name,
            "priority_score": self.priority_score,
            "reason_codes": self.reason_codes,
        }
        if self.context:
            d["context"] = self.context.to_dict()
        return d


@dataclass
class PrioritizationOutput:
    run_id: str
    store_id: str
    selected_skus: List[PrioritySKU]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "store_id": self.store_id,
            "selected_skus": [s.to_dict() for s in self.selected_skus],
        }


# -------------------------------------------------------------
# AI Reasoning Output Schema (Bedrock Claude 3.5 Sonnet)
# -------------------------------------------------------------
@dataclass
class AIRecommendationOutput:
    recommended_qty: int
    normal_qty: int
    adjusted_qty_before_moq: int
    moq_applied: bool = False
    packaging_multiple_applied: bool = False
    confidence_score: float = 0.85
    risk_level: str = "medium"  # low, medium, high
    reasoning_narrative: str = ""
    key_factors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    prompt_version: str = "v1.0"
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -------------------------------------------------------------
# Telegram State Machine Schema
# -------------------------------------------------------------
TelegramStatus = Literal[
    "PENDING_APPROVAL",
    "AWAITING_QTY",
    "AWAITING_REJECT_REASON",
    "APPROVED",
    "EDITED",
    "REJECTED",
    "TIMEOUT",
    "FAILED_SAP",
    "QUEUED_SAP",
    "PR_CREATED"
]

# Values for awaiting_input
AWAITING_QTY = "QTY"
AWAITING_REJECT_REASON = "REJECT_REASON"


@dataclass
class TelegramStateRecord:
    request_id: str
    run_id: str
    store_id: str
    sku_id: str
    recommended_qty: int
    telegram_chat_id: str
    created_at: str
    expires_at: str
    final_qty: Optional[int] = None
    status: str = "PENDING_APPROVAL"
    telegram_message_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    sap_pr_id: Optional[str] = None
    sap_error_message: Optional[str] = None
    # Set when the bot is waiting for a free-text reply (EDIT qty / REJECT reason).
    awaiting_input: Optional[str] = None
    PK: str = ""
    SK: str = "STATE"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"REQ#{self.request_id}"
        d["SK"] = "STATE"
        return d


# -------------------------------------------------------------
# SAP S/4HANA OData PR Schemas
# -------------------------------------------------------------
@dataclass
class SapPRItem:
    Material: str
    Plant: str
    StoreLocation: str
    RequestedQuantity: int
    BaseUnit: str = "PCS"
    DeliveryDate: str = ""  # YYYY-MM-DD
    ShortText: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SapPRPayload:
    PurchaseRequisitionType: str = "NB"
    PurchaseRequisitionItems: List[SapPRItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "PurchaseRequisitionType": self.PurchaseRequisitionType,
            "PurchaseRequisitionItems": [i.to_dict() for i in self.PurchaseRequisitionItems],
        }


@dataclass
class SapPRResponse:
    success: bool
    sap_pr_id: Optional[str] = None
    error_message: Optional[str] = None
    status_code: int = 200
    timestamp: str = ""
    # "LIVE" when a real S/4HANA system responded, "PERSISTENT_SANDBOX" for the
    # credential-less sandbox mode that still persists to DynamoDB.
    mode: str = "LIVE"
    # Raw OData response envelope ({"d": {...}}) for audit traceability.
    odata_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -------------------------------------------------------------
# SAP Transaction Ledger (idempotency + audit for both modes)
# -------------------------------------------------------------
@dataclass
class SapTransactionRecord:
    request_id: str
    store_id: str
    sku_id: str
    quantity: int
    status: str  # SUCCESS, FAILED
    mode: str  # LIVE | PERSISTENT_SANDBOX
    created_at: str
    # Optional: absent on a failed attempt. Defaulted so that failed ledger
    # entries survive the ``_clean()`` null-stripping and can be rehydrated.
    sap_pr_id: Optional[str] = None
    response_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"SAPTRANS#{self.request_id}"
        d["SK"] = "TRANSACTION"
        d["GSI1PK"] = "SAPTRANS"
        d["GSI1SK"] = f"{self.created_at}#{self.request_id}"
        if self.sap_pr_id:
            d["GSI2PK"] = f"SAPPR#{self.sap_pr_id}"
            d["GSI2SK"] = self.created_at
        return d


# -------------------------------------------------------------
# Audit & Feedback Schemas
# -------------------------------------------------------------
@dataclass
class AuditLogRecord:
    request_id: str
    run_id: str
    store_id: str
    store_name: str
    area_type: str
    sku_id: str
    sku_name: str
    category: str
    physical_stock: int
    threshold: int
    average_daily_burn_rate: float
    lead_time_days: int
    moq: int
    packaging_multiple: int
    weather_condition: str
    weather_source: str
    weather_stale: bool
    calendar_day: str
    is_public_holiday: bool
    is_payday: bool
    promo_active: bool
    created_at: str
    prompt_version: str = "v1.0"
    model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    ai_recommended_qty: int = 0
    normal_qty: int = 0
    adjusted_qty_before_moq: int = 0
    final_recommended_qty: int = 0
    moq_applied: bool = False
    packaging_multiple_applied: bool = False
    confidence_score: float = 0.85
    risk_level: str = "medium"
    reasoning_narrative: str = ""
    key_factors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Provenance of the reasoning: True when Bedrock was unreachable and the
    # deterministic rule-based engine produced the recommendation.
    is_fallback: bool = False
    promo_type: Optional[str] = None
    human_action: Optional[str] = None  # APPROVED, EDITED, REJECTED, TIMEOUT
    human_final_qty: Optional[int] = None
    rejection_reason: Optional[str] = None
    sap_pr_status: str = "PENDING"  # PENDING, QUEUED, SUCCESS, FAILED_SAP
    sap_pr_id: Optional[str] = None
    sap_mode: Optional[str] = None  # LIVE | PERSISTENT_SANDBOX
    approved_at: Optional[str] = None
    completed_at: Optional[str] = None
    PK: str = ""
    SK: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"AUDIT#{self.store_id}"
        d["SK"] = f"TS#{self.created_at}#SKU#{self.sku_id}"
        d["GSI1PK"] = "AUDIT"
        d["GSI1SK"] = f"{self.created_at}#{self.request_id}"
        d["GSI2PK"] = f"AUDIT#{self.request_id}"
        d["GSI2SK"] = self.created_at
        return d


@dataclass
class FeedbackLogRecord:
    store_id: str
    sku_id: str
    action: str  # APPROVED, EDITED or REJECTED
    reason: str
    original_recommended_qty: int
    created_at: str
    final_qty: Optional[int] = None
    PK: str = ""
    SK: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"FEEDBACK#{self.store_id}#{self.sku_id}"
        d["SK"] = f"TS#{self.created_at}"
        d["GSI1PK"] = "FEEDBACK"
        d["GSI1SK"] = f"{self.created_at}#{self.store_id}#{self.sku_id}"
        return d
