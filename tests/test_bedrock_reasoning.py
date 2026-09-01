"""Unit Tests for Bedrock Reasoning Engine & Guardrails (PRD Section 11.5 & 16)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.services.bedrock_service import BedrockReasoningService
from src.models.schema import (
    AggregationContext,
    StoreProfile,
    SKUContext,
    ExternalContext,
    WeatherContext,
    CalendarContext,
    PromoContext,
)

class TestBedrockReasoning(unittest.TestCase):

    def setUp(self):
        self.service = BedrockReasoningService()
        self.context = AggregationContext(
            store=StoreProfile(
                store_id="STR-001",
                store_name="Cabang Sudirman",
                area_type="Perkantoran",
                zone="JAKARTA_PUSAT",
                telegram_chat_id="chat_001"
            ),
            sku=SKUContext(
                sku_id="SKU-10023",
                sku_name="Roti Manis Cokelat 100g",
                category="Perishable",
                physical_stock=12,
                threshold=20,
                average_daily_burn_rate=25.0,
                lead_time_days=2,
                moq=12,
                packaging_multiple=12
            ),
            external_context=ExternalContext(
                weather=WeatherContext(condition="Hujan deras", temperature_c=27.0, rain_probability=0.85),
                calendar=CalendarContext(day_type="Weekend", day_of_week="Saturday"),
                promo=PromoContext(is_active=False)
            )
        )

    def test_json_validation_strict_parsing(self):
        """Strict JSON parsing validates valid schema correctly."""
        valid_json = """{
            "recommended_qty": 15,
            "normal_qty": 50,
            "adjusted_qty_before_moq": 15,
            "moq_applied": false,
            "packaging_multiple_applied": true,
            "confidence_score": 0.87,
            "risk_level": "medium",
            "reasoning_narrative": "Stok di bawah threshold, kuota dipotong saat weekend.",
            "key_factors": ["below_threshold", "heavy_rain"],
            "warnings": ["SKU perishable"]
        }"""
        parsed = self.service._parse_and_validate_json(valid_json)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.recommended_qty, 15)
        self.assertEqual(parsed.confidence_score, 0.87)

    def test_invalid_json_returns_none_and_triggers_fallback(self):
        """Malformed JSON is rejected safely."""
        invalid_json = "NOT_A_VALID_JSON_STRING"
        parsed = self.service._parse_and_validate_json(invalid_json)
        self.assertIsNone(parsed)

    def test_perishable_weekend_office_conservative_recommendation(self):
        """Rule-based engine produces conservative quantity for office area on weekend with rain."""
        rec = self.service._rule_based_fallback(self.context)
        self.assertLess(rec.recommended_qty, rec.normal_qty)
        self.assertIn("perishable", self.context.sku.category.lower())
        self.assertTrue(rec.is_fallback)
        self.assertIn("Stok di bawah threshold", rec.reasoning_narrative)

if __name__ == "__main__":
    unittest.main()
