"""Unit Tests for MOQ and Packaging Multiple Logic (PRD Section 11.6 & 20.1)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.services.moq_packaging_service import MoqPackagingService

class TestMoqPackaging(unittest.TestCase):

    def test_non_perishable_round_up(self):
        """Non-perishable items round up to nearest packaging multiple."""
        final_qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=15,
            moq=12,
            packaging_multiple=12,
            category="Non-Perishable"
        )
        self.assertEqual(final_qty, 24)
        self.assertTrue(pack_app)
        self.assertFalse(moq_app)

    def test_moq_enforcement_under_moq(self):
        """Quantity below MOQ is adjusted to MOQ minimum."""
        final_qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=5,
            moq=12,
            packaging_multiple=12,
            category="Non-Perishable"
        )
        self.assertEqual(final_qty, 12)
        self.assertTrue(moq_app)

    def test_perishable_conservative_rounding(self):
        """Perishable item with high spoilage risk rounds conservatively."""
        final_qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=15,
            moq=12,
            packaging_multiple=12,
            category="Perishable",
            risk_level="high",
            area_type="Perkantoran",
            weather_condition="Hujan deras"
        )
        self.assertEqual(final_qty, 12)
        self.assertTrue(pack_app)

    def test_zero_quantity_no_adjustment(self):
        """Zero quantity results in 0 order."""
        final_qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=0,
            moq=12,
            packaging_multiple=12
        )
        self.assertEqual(final_qty, 0)

if __name__ == "__main__":
    unittest.main()
