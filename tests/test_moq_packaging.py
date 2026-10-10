"""MOQ & Packaging Multiple adjustment tests (PRD Section 11.6, 15.2).

Rounding rules must protect the store from spoilage and breakage: perishables,
short shelf-life goods, and fragile items round DOWN to a valid pack, while
non-perishables round UP.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from src.services.moq_packaging_service import MoqPackagingService


class TestMoqPackaging(unittest.TestCase):

    # ---------------------------------------------------------
    # Non-perishables round up
    # ---------------------------------------------------------
    def test_beras_rounds_up_to_karung_multiple(self):
        qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=13, moq=5, packaging_multiple=5, category="Non-Perishable",
        )
        self.assertEqual(qty, 15)
        self.assertTrue(pack_app)
        self.assertFalse(moq_app)

    def test_gula_rounds_up_to_sak_multiple(self):
        qty, _, pack_app, _ = MoqPackagingService.adjust_quantity(
            raw_qty=38, moq=20, packaging_multiple=20, category="Non-Perishable",
        )
        self.assertEqual(qty, 40)
        self.assertTrue(pack_app)

    def test_minyak_rounds_to_kardus_multiple(self):
        qty, _, _, _ = MoqPackagingService.adjust_quantity(
            raw_qty=25, moq=12, packaging_multiple=12, category="Non-Perishable",
        )
        self.assertEqual(qty, 36)

    def test_zero_quantity_returns_zero(self):
        qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(0, 5, 5)
        self.assertEqual(qty, 0)
        self.assertFalse(moq_app)
        self.assertFalse(pack_app)

    def test_negative_quantity_returns_zero(self):
        self.assertEqual(MoqPackagingService.adjust_quantity(-4, 5, 5)[0], 0)

    # ---------------------------------------------------------
    # MOQ flooring
    # ---------------------------------------------------------
    def test_moq_floors_small_quantities(self):
        qty, moq_app, _, note = MoqPackagingService.adjust_quantity(
            raw_qty=3, moq=20, packaging_multiple=20, category="Non-Perishable",
        )
        self.assertEqual(qty, 20)
        self.assertTrue(moq_app)
        self.assertIn("MOQ 20", note)

    def test_perishable_high_risk_floors_to_smallest_valid_pack(self):
        """Perishable + high risk must not be forced to the full MOQ."""
        qty, moq_app, _, _ = MoqPackagingService.adjust_quantity(
            raw_qty=2, moq=12, packaging_multiple=12,
            category="Perishable", risk_level="high",
        )
        self.assertEqual(qty, 12)
        self.assertTrue(moq_app)

    # ---------------------------------------------------------
    # Conservative rounding for spoilage / breakage risk
    # ---------------------------------------------------------
    def test_telur_fragile_rounds_down(self):
        """23 trays -> 20: a fragile/perishable SKU must not round up."""
        qty, _, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=23, moq=10, packaging_multiple=10,
            category="Perishable", risk_level="medium", is_fragile=True,
        )
        self.assertEqual(qty, 20)
        self.assertTrue(pack_app)
        self.assertIn("ke bawah", note)
        self.assertIn("mudah pecah", note)

    def test_short_shelf_life_rounds_down(self):
        qty, _, _, note = MoqPackagingService.adjust_quantity(
            raw_qty=29, moq=12, packaging_multiple=12,
            category="Perishable", risk_level="medium", shelf_life_days=3,
        )
        self.assertEqual(qty, 24)
        self.assertIn("shelf life 3 hari", note)

    def test_beras_long_shelf_life_rounds_up_even_if_perishable_flag(self):
        """A 365-day shelf life must not trigger conservative rounding."""
        qty, _, _, note = MoqPackagingService.adjust_quantity(
            raw_qty=13, moq=5, packaging_multiple=5,
            category="Non-Perishable", risk_level="medium", shelf_life_days=365,
        )
        self.assertEqual(qty, 15)
        self.assertNotIn("ke bawah", note)

    def test_note_mentions_both_constraints(self):
        _, moq_app, _, note = MoqPackagingService.adjust_quantity(
            raw_qty=4, moq=12, packaging_multiple=12,
            category="Perishable", risk_level="medium", shelf_life_days=3, is_fragile=True,
        )
        _, _, _, note = MoqPackagingService.adjust_quantity(
            raw_qty=4, moq=12, packaging_multiple=12,
            category="Perishable", risk_level="medium", shelf_life_days=3, is_fragile=True,
        )
        self.assertIn("shelf life 3 hari", note)
        self.assertIn("mudah pecah", note)

    def test_exact_multiple_is_untouched(self):
        qty, moq_app, pack_app, note = MoqPackagingService.adjust_quantity(
            raw_qty=30, moq=10, packaging_multiple=10,
            category="Perishable", is_fragile=True, risk_level="medium",
        )
        self.assertEqual(qty, 30)
        self.assertFalse(pack_app)

    def test_returns_four_tuple_contract(self):
        result = MoqPackagingService.adjust_quantity(13, 5, 5)
        self.assertEqual(len(result), 4)
        qty, moq_app, pack_app, note = result
        self.assertIsInstance(qty, int)
        self.assertIsInstance(moq_app, bool)
        self.assertIsInstance(pack_app, bool)
        self.assertIsInstance(note, str)


if __name__ == "__main__":
    unittest.main()
