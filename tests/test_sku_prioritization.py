"""Unit Tests for SKU Prioritization Logic (PRD Section 11.2 FR-02)."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from conftest import create_test_orchestrator, get_test_store, get_test_sku_perishable
from src.models.schema import SKUProfile

class TestSkuPrioritization(unittest.TestCase):

    def setUp(self):
        services = create_test_orchestrator()
        self.orchestrator = services["orchestrator"]
        self.store = get_test_store()
        self.sku_perishable = get_test_sku_perishable()
        self.sku_stable = SKUProfile(
            sku_id="SKU-STABLE-999",
            sku_name="Plastik Sampah Roll",
            category="Non-Perishable",
            weather_sensitive=False,
            moq=5,
            packaging_multiple=5,
            default_lead_time_days=1
        )

    def test_stock_below_threshold_priority(self):
        """SKU with stock below threshold receives high priority score."""
        stock_levels = {
            self.sku_perishable.sku_id: {
                "physical_stock": 5,
                "threshold": 20,
                "average_daily_burn_rate": 20.0,
                "lead_time_days": 2,
                "open_pr_qty": 0
            }
        }
        priorities = self.orchestrator.prioritize_skus(self.store, [self.sku_perishable], stock_levels)
        self.assertEqual(len(priorities), 1)
        self.assertIn("below_threshold", priorities[0].reason_codes)
        self.assertIn("perishable", priorities[0].reason_codes)
        self.assertGreater(priorities[0].priority_score, 60)

    def test_healthy_sku_filtered_out(self):
        """SKU with abundant stock and no risk signals is not selected."""
        stock_levels = {
            self.sku_stable.sku_id: {
                "physical_stock": 100,
                "threshold": 20,
                "average_daily_burn_rate": 2.0,
                "lead_time_days": 1,
                "open_pr_qty": 0
            }
        }
        priorities = self.orchestrator.prioritize_skus(self.store, [self.sku_stable], stock_levels)
        self.assertEqual(len(priorities), 0)

    def test_cold_start_flag_handling(self):
        """SKU in cold start state is tagged and prioritized with cold_start reason code."""
        stock_levels = {
            self.sku_stable.sku_id: {
                "physical_stock": 10,
                "threshold": 20,
                "average_daily_burn_rate": 10.0,
                "lead_time_days": 2,
                "is_cold_start": True
            }
        }
        priorities = self.orchestrator.prioritize_skus(self.store, [self.sku_stable], stock_levels)
        self.assertEqual(len(priorities), 1)
        self.assertIn("cold_start", priorities[0].reason_codes)

if __name__ == "__main__":
    unittest.main()
