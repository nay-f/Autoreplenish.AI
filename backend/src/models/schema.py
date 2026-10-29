from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class PromoItem(BaseModel):
    promo_id: str = Field(min_length=2, max_length=64)
    promo_name: str = Field(min_length=2, max_length=120)
    promo_type: str = Field(default="JSM / Weekend", max_length=60)
    start_date: str = Field(min_length=8, max_length=20)
    end_date: str = Field(min_length=8, max_length=20)
    target_sku_ids: List[str] = []


class LocalEventItem(BaseModel):
    event_id: str = Field(min_length=2, max_length=64)
    event_name: str = Field(min_length=2, max_length=120)
    event_date: str = Field(min_length=8, max_length=20)
    impact_multiplier: float = Field(default=1.2, ge=0.5, le=5.0)


class StoreProfile(BaseModel):
    store_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    store_name: str = Field(min_length=2, max_length=120)
    area_type: str = Field(default="Komersial / Perkantoran", max_length=80)
    zone: str = Field(default="ZONE-SMG-01", min_length=2, max_length=64)
    latitude: float = Field(default=-6.9666, ge=-90.0, le=90.0)
    longitude: float = Field(default=110.4166, ge=-180.0, le=180.0)
    telegram_chat_id: str = Field(default="", max_length=64)

    # Tab 2: Koneksi Sumber Data Inventaris
    ingestion_mode: Literal["POS_LOCAL", "SAP_BTP"] = "POS_LOCAL"
    pos_connector_type: str = Field(default="REST Webhook", max_length=80)
    pos_sync_schedule: str = Field(default="21:00", max_length=60)
    sap_odata_url: str = Field(default="", max_length=500)
    sap_plant: str = Field(default="1000", min_length=2, max_length=20)
    sap_storage_location: str = Field(default="WH01", min_length=2, max_length=20)
    sap_purchasing_org: str = Field(default="1000", min_length=2, max_length=20)

    # Tab 3: Kanal Validasi HITL
    timeout_tolerance_hours: int = Field(default=4, ge=1, le=48)
    enable_auto_reminder: bool = True

    # Tab 5: Kalender Promo & Event Lokal
    promos: List[PromoItem] = []
    local_events: List[LocalEventItem] = []
    active: bool = True


class SKUItem(BaseModel):
    sku_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    sku_name: str = Field(min_length=2, max_length=120)
    category: str = Field(default="Daily Staples", max_length=60)
    physical_stock: int = Field(ge=0, le=1000000)
    threshold: int = Field(ge=0, le=1000000)
    average_daily_burn_rate: float = Field(ge=0.0, le=100000.0)
    lead_time_days: int = Field(default=2, ge=0, le=365)
    delivery_window: List[str] = ["Senin", "Rabu", "Jumat"]
    moq: int = Field(default=1, ge=1, le=100000)
    packaging_multiple: int = Field(default=1, ge=1, le=100000)
    unit_price: float = Field(default=15000.0, gt=0.0, le=100000000.0)
    currency: str = Field(default="IDR", min_length=3, max_length=5)
    shelf_life_days: Optional[int] = Field(default=None, ge=0, le=3650)
    is_perishable: bool = False


class AIRecommendation(BaseModel):
    recommended_qty: int = Field(ge=0, le=100000)
    normal_qty: int = Field(ge=0, le=100000)
    deterministic_baseline_qty: int = Field(default=0, ge=0, le=100000)
    ai_unconstrained_qty: int = Field(default=0, ge=0, le=100000)
    adjusted_qty_before_moq: int = Field(ge=0, le=100000)
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_tier: Literal["HIGH_CONFIDENCE", "MANUAL_REVIEW_REQUIRED", "LOW_CONFIDENCE_GUARDRAILED"] = "MANUAL_REVIEW_REQUIRED"
    risk_level: Literal["low", "medium", "high"] = "medium"
    reasoning_narrative: str
    key_factors: List[str] = []
    warnings: List[str] = []
    guardrail_applied: bool = False
    is_fallback: bool = False
    model_id: str = ""
    prompt_version: str = ""
    latency_ms: int = 0
    failure_class: Optional[str] = None

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk(cls, v):
        val = str(v).lower().strip()
        return val if val in ("low", "medium", "high") else "medium"


class TelegramApprovalState(BaseModel):
    request_id: str
    store_id: str
    sku_id: str
    sku_name: str = ""
    recommended_qty: int = Field(ge=0, le=100000)
    final_qty: Optional[int] = Field(default=None, ge=0, le=100000)
    status: Literal[
        "PENDING_APPROVAL",
        "EDIT_REQUESTED",
        "APPROVED",
        "QUEUE_FAILED",
        "EDITED",
        "REJECTED",
        "ENQUEUED",
        "PROCESSING",
        "SAP_SUBMITTING",
        "SAP_SUBMITTED",
        "SAP_SANDBOX_VERIFIED",
        "SAP_DRY_RUN",
        "SAP_FAILED",
        "TIMEOUT",
    ] = "PENDING_APPROVAL"
    rejection_reason: Optional[str] = None
    sap_pr_id: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_message_id: Optional[int] = None
    created_at: str
    expires_at: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    role: Literal[
        "Store Manager",
        "Regional Manager",
        "IT Administrator",
        "Auditor",
    ] = "Store Manager"
