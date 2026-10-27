import os
import pytest
from pydantic import ValidationError

from backend.src.models.schema import StoreProfile, SKUItem, AIRecommendation
from backend.src.services.moq_packaging_service import MOQPackagingService
from backend.src.services.bedrock_service import BedrockReasoningService
from backend.src.services.dynamodb_service import VALID_STATE_TRANSITIONS
from backend.src.auth import verify_password, create_access_token
import backend.src.config as config


def test_moq_and_packaging_rounding_non_perishable():
    """Barang non-perishable wajib dibulatkan ke atas sesuai kelipatan kardus."""
    sku = SKUItem(
        sku_id="SKU-MINYAK-01",
        sku_name="Minyak Goreng 2L",
        physical_stock=5,
        threshold=20,
        average_daily_burn_rate=10.0,
        moq=12,
        packaging_multiple=12,
        unit_price=34000.0,
        is_perishable=False,
    )
    # AI merekomendasikan 25 -> dibulatkan ke atas kelipatan 12 menjadi 36
    res = MOQPackagingService.adjust_quantity(sku, ai_qty=25, risk_level="medium")
    assert res["final_qty"] == 36
    assert res["packaging_multiple_applied"] is True


def test_moq_and_packaging_conservative_perishable_high_risk():
    """Barang segar (perishable) saat risiko tinggi wajib dibulatkan konservatif ke bawah."""
    sku = SKUItem(
        sku_id="SKU-ROTI-01",
        sku_name="Roti Tawar Kupas",
        physical_stock=5,
        threshold=20,
        average_daily_burn_rate=10.0,
        moq=10,
        packaging_multiple=10,
        unit_price=14000.0,
        is_perishable=True,
        shelf_life_days=3,
    )
    # AI merekomendasikan 28 saat risiko tinggi -> dibulatkan konservatif ke 20 (bukan 30)
    res = MOQPackagingService.adjust_quantity(sku, ai_qty=28, risk_level="high")
    assert res["final_qty"] == 20


def test_deterministic_baseline_and_guardrail_bounds():
    """Pastikan Python menghitung baseline dan batas guardrail atas/bawah dengan akurat."""
    sku = SKUItem(
        sku_id="SKU-BERAS-01",
        sku_name="Beras Ramos 5kg",
        physical_stock=10,
        threshold=30,
        average_daily_burn_rate=5.0,
        lead_time_days=2,
        moq=5,
        packaging_multiple=5,
        unit_price=68000.0,
    )
    # Defisit = 30 - 10 = 20; Lead time demand = 5 * 2 = 10 -> Baseline = 30
    baseline = BedrockReasoningService.calculate_deterministic_baseline(sku)
    assert baseline["stock_deficit"] == 20
    assert baseline["lead_time_demand"] == 10
    assert baseline["baseline_qty"] == 30
    assert baseline["max_allowed_qty"] == int(30 * config.AI_MAX_MULTIPLIER_CAP)


def test_pydantic_strict_input_validation():
    """Pastikan koordinat GPS tidak valid atau harga <= 0 ditolak oleh Pydantic."""
    with pytest.raises(ValidationError):
        StoreProfile(
            store_id="STR-INVALID",
            store_name="TokoSalahGPS",
            latitude=125.0,  # Tidak valid (> 90)
            longitude=110.0,
        )

    with pytest.raises(ValidationError):
        SKUItem(
            sku_id="SKU-NEG",
            sku_name="Barang Harga Nol",
            physical_stock=10,
            threshold=10,
            average_daily_burn_rate=2.0,
            unit_price=0.0,  # Tidak valid (wajib > 0)
        )


def test_jwt_and_password_hash_verification():
    """Pastikan bcrypt hash dan pembuatan token JWT berjalan benar."""
    raw_pw = os.getenv("ADMIN_PASSWORD", "admin123") if "os" in globals() else "admin123"
    assert verify_password(raw_pw, config.ADMIN_PASSWORD_HASH) is True
    assert verify_password("password_salah", config.ADMIN_PASSWORD_HASH) is False

    token = create_access_token("admin", "Store Manager")
    assert isinstance(token, str) and len(token) > 20


def test_approval_state_machine_rules():
    """Pastikan state REJECTED tidak bisa melompat langsung menjadi SAP_SUBMITTED."""
    allowed_from_pending = VALID_STATE_TRANSITIONS["PENDING_APPROVAL"]
    assert "SAP_SUBMITTING" in allowed_from_pending
    assert "REJECTED" in allowed_from_pending
    assert "REJECTED" not in VALID_STATE_TRANSITIONS