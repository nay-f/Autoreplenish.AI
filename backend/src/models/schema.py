"""Data Models & Schemas for AutoReplenish.ai.

Defines all structures for Store, SKU, External Signals, AI Reasoning,
Telegram State Machine, SAP OData PR payload, and Audit Logging.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any
import json

# -------------------------------------------------------------
# Store & SKU Metadata
# -------------------------------------------------------------
@dataclass
class StoreProfile:
    store_id: str
    store_name: str
    area_type: str = "Perkantoran"  # Perkantoran, Perumahan, Kampus
    zone: str = "JAKARTA_PUSAT"
    sap_plant: str = "1000"
    storage_location: str = "STR-001"
    telegram_chat_id: str = "123456789"
    active: bool = True
    PK: str = ""
    SK: str = "PROFILE"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"STORE#{self.store_id}"
        d["SK"] = "PROFILE"
        return d


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
    PK: str = ""
    SK: str = "PROFILE"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"SKU#{self.sku_id}"
        d["SK"] = "PROFILE"
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
    "APPROVED",
    "EDITED",
    "REJECTED",
    "TIMEOUT",
    "FAILED_SAP",
    "PR_CREATED"
]


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    model: str = "anthropic.claude-3-5-sonnet"
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
    promo_type: Optional[str] = None
    human_action: Optional[str] = None  # APPROVED, EDITED, REJECTED, TIMEOUT
    human_final_qty: Optional[int] = None
    rejection_reason: Optional[str] = None
    sap_pr_status: str = "PENDING"  # PENDING, SUCCESS, FAILED_SAP
    sap_pr_id: Optional[str] = None
    approved_at: Optional[str] = None
    completed_at: Optional[str] = None
    PK: str = ""
    SK: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["PK"] = f"AUDIT#{self.store_id}"
        d["SK"] = f"TS#{self.created_at}#SKU#{self.sku_id}"
        return d


@dataclass
class FeedbackLogRecord:
    store_id: str
    sku_id: str
    action: str  # REJECTED or EDITED
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
        return d
