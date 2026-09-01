"""Mock AWS Bedrock Reasoning Service (Claude 3.5 Sonnet) for AutoReplenish.ai Demo.

Implements deterministic multi-variable reasoning (PRD Section 11.5, 16.1, and 19.1)
without calling real AWS Bedrock APIs.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List


def invoke_bedrock(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate Claude 3.5 Sonnet context-aware reasoning on replenishing inventory.

    Args:
        context: Aggregation context containing store, sku, inventory, weather, calendar.

    Returns:
        Structured JSON matching AI recommendation output schema (PRD Section 11.5).
    """
    store = context.get("store", {})
    sku = context.get("sku", {})
    inv = context.get("inventory", {})
    weather = context.get("weather", {})
    calendar = context.get("calendar", {})

    store_name = store.get("store_name", "Toko")
    area_type = str(store.get("area_type", "Umum"))
    
    sku_name = sku.get("sku_name", "Barang")
    category = str(sku.get("category", "Non-Perishable"))
    is_perishable = category.strip().lower() == "perishable"
    weather_sensitive = bool(sku.get("weather_sensitive", False))
    moq = int(sku.get("moq", 1))
    packaging_multiple = max(1, int(sku.get("packaging_multiple", 1)))
    lead_time = int(sku.get("default_lead_time_days", sku.get("lead_time_days", 1)))

    physical_stock = int(inv.get("physical_stock", 0))
    threshold = int(inv.get("threshold", 0))
    burn_rate = max(1, int(inv.get("average_daily_burn_rate", 1)))

    weather_condition = str(weather.get("condition", "Cerah"))
    rain_probability = float(weather.get("rain_probability", 0.0))
    day_type = str(calendar.get("day_type", "Weekday"))

    # 1. Base demand calculation: normal_qty = burn_rate * (lead_time + 1)
    normal_qty = max(moq, int(burn_rate * (lead_time + 1)))

    # 2. Context adjustment factor
    adjustment_factor = 1.0
    key_factors: List[str] = []
    warnings: List[str] = []

    if physical_stock < threshold:
        key_factors.append("below_threshold")

    if weather_sensitive:
        key_factors.append("weather_sensitive")

    if lead_time >= 2:
        key_factors.append(f"lead_time_{lead_time}_days")

    if is_perishable:
        key_factors.append("perishable_sku")
        warnings.append("Risiko pembusukan/kedaluwarsa tinggi jika kuota berlebih")

    # Weather Factor
    is_rainy = "hujan" in weather_condition.lower() or rain_probability > 0.6
    if is_rainy:
        adjustment_factor *= 0.6
        key_factors.append("heavy_rain")

    # Calendar & Demographic Factor
    area_lower = area_type.strip().lower()
    if day_type == "Weekend":
        if area_lower == "perkantoran":
            adjustment_factor *= 0.5
            key_factors.append("weekend_office_area_quiet")
            warnings.append("Aktivitas kantor libur di akhir pekan")
        elif area_lower == "perumahan":
            adjustment_factor *= 1.1
            key_factors.append("weekend_residential_busy")
        elif area_lower == "kampus":
            adjustment_factor *= 0.7
            key_factors.append("weekend_campus_quiet")
    else:
        if area_lower == "perkantoran":
            adjustment_factor *= 1.1
            key_factors.append("weekday_office_traffic")

    # 3. Raw adjusted quantity calculation
    adjusted_qty = max(1, int(round(normal_qty * adjustment_factor)))
    adjusted_qty_before_moq = adjusted_qty

    # 4. Packaging Multiple constraint
    packaging_multiple_applied = False
    if packaging_multiple > 1 and (adjusted_qty % packaging_multiple != 0):
        packaging_multiple_applied = True
        if is_perishable:
            # Conservative downward rounding for perishable items
            rounded_qty = (adjusted_qty // packaging_multiple) * packaging_multiple
            adjusted_qty = max(packaging_multiple, rounded_qty)
        else:
            # Upward rounding for non-perishable items
            adjusted_qty = int(math.ceil(adjusted_qty / packaging_multiple) * packaging_multiple)

    # 5. MOQ constraint
    moq_applied = False
    if adjusted_qty < moq:
        moq_applied = True
        adjusted_qty = moq
        if is_perishable and adjustment_factor < 0.6:
            warnings.append(f"Jumlah disesuaikan ke batas MOQ ({moq} Pcs) meskipun estimasi kebutuhan rendah")

    recommended_qty = adjusted_qty

    # 6. Confidence Score
    confidence = 0.87
    confidence -= (len(warnings) * 0.05)
    if adjustment_factor < 0.5:
        confidence -= 0.05
    confidence = round(max(0.50, min(0.95, confidence)), 2)

    # 7. Risk Level
    if confidence >= 0.80 and len(warnings) == 0:
        risk_level = "low"
    elif confidence >= 0.70:
        risk_level = "medium"
    else:
        risk_level = "high"

    # 8. Indonesian Reasoning Narrative
    if is_perishable and area_lower == "perkantoran" and day_type == "Weekend":
        narrative = (
            f"Stok fisik ({physical_stock} Pcs) berada di bawah batas minimum ({threshold} Pcs). "
            f"Namun, toko berada di area perkantoran yang sepi saat akhir pekan ({day_type}) "
            f"disertai perkiraan cuaca {weather_condition.lower()} ({int(rain_probability * 100)}% potensi hujan). "
            f"Untuk mencegah risiko pembusukan/waste kategori perishable, kuota normal ({normal_qty} Pcs) "
            f"dipangkas menjadi {recommended_qty} Pcs."
        )
    elif area_lower == "perumahan" and day_type == "Weekend":
        narrative = (
            f"Stok fisik ({physical_stock} Pcs) berada di bawah threshold ({threshold} Pcs). "
            f"Area perumahan menunjukkan kenaikan transaksi rumah tangga saat akhir pekan. "
            f"Direkomendasikan order sebanyak {recommended_qty} Pcs untuk menjaga ketersediaan hingga pengiriman berikutnya."
        )
    elif area_lower == "kampus" and day_type == "Weekend":
        narrative = (
            f"Stok fisik ({physical_stock} Pcs) mendekati batas minimum ({threshold} Pcs). "
            f"Aktivitas mahasiswa berkurang saat akhir pekan. Kuota disesuaikan ke {recommended_qty} Pcs sesuai kelipatan kemasan."
        )
    else:
        narrative = (
            f"Stok fisik ({physical_stock} Pcs) di bawah threshold ({threshold} Pcs). "
            f"Rekomendasi dihitung berdasarkan laju konsumsi {burn_rate} Pcs/hari dan lead time supplier {lead_time} hari "
            f"dengan mempertimbangkan kondisi operasional toko {store_name}."
        )

    return {
        "recommended_qty": recommended_qty,
        "normal_qty": normal_qty,
        "adjusted_qty_before_moq": adjusted_qty_before_moq,
        "moq_applied": moq_applied,
        "packaging_multiple_applied": packaging_multiple_applied,
        "confidence_score": confidence,
        "risk_level": risk_level,
        "reasoning_narrative": narrative,
        "key_factors": key_factors,
        "warnings": warnings,
    }


def get_prompt_info() -> Dict[str, Any]:
    """Return prompt metadata for audit trail logging (PRD Section 11.12 & 28)."""
    return {
        "prompt_version": "v1.0",
        "model": "anthropic.claude-3-5-sonnet",
        "temperature": 0.2,
        "max_tokens": 1024,
        "output_format": "strict_json",
        "invoked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock_bedrock",
    }
