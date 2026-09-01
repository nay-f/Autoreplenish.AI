"""MOQ and Packaging Multiple Adjustment Service.

Implements PRD Section 11.6 and 15.2:
- Adjusts AI raw recommended quantity to valid procurement quantities (MOQ and case/pack multiples).
- Conservative rounding rules for perishable SKUs to prevent spoilage.
"""

import math
import logging
from typing import Dict, Any, Tuple
from ..config import logger

class MoqPackagingService:
    """Calculates procurement-compliant order quantities."""

    @staticmethod
    def adjust_quantity(
        raw_qty: int,
        moq: int,
        packaging_multiple: int,
        category: str = "Non-Perishable",
        risk_level: str = "medium",
        area_type: str = "Perkantoran",
        weather_condition: str = "Cerah"
    ) -> Tuple[int, bool, bool, str]:
        """
        Adjust raw quantity.
        Returns:
            final_qty (int): adjusted procurement quantity
            moq_applied (bool): whether MOQ forced an increase
            packaging_applied (bool): whether packaging multiple adjusted the qty
            note (str): explanation of adjustment
        """
        if raw_qty <= 0:
            return 0, False, False, "Kebutuhan stok terpenuhi (0 pcs)"

        moq = max(1, moq)
        packaging_multiple = max(1, packaging_multiple)

        moq_applied = False
        packaging_applied = False
        adjusted_qty = raw_qty

        # 1. Evaluate MOQ
        if adjusted_qty < moq:
            if category.lower() == "perishable" and risk_level == "high":
                # For perishable with high risk (e.g. weekend rain in office area), keep conservative
                logger.info(f"Perishable SKU under MOQ ({adjusted_qty} < {moq}) with high risk. Applying minimum pack.")
                adjusted_qty = moq
                moq_applied = True
            else:
                adjusted_qty = moq
                moq_applied = True

        # 2. Packaging multiple rounding
        rem = adjusted_qty % packaging_multiple
        if rem != 0:
            packaging_applied = True
            if category.lower() == "perishable" and risk_level in ("high", "medium"):
                # Check if rounding up causes excessive inventory for perishable
                round_down_qty = (adjusted_qty // packaging_multiple) * packaging_multiple
                round_up_qty = round_down_qty + packaging_multiple

                # If round_down is at least MOQ, consider conservative rounding
                if round_down_qty >= moq and (round_up_qty - adjusted_qty) > (packaging_multiple / 2):
                    adjusted_qty = round_down_qty
                    note = f"Dibulatkan ke bawah ({adjusted_qty} pcs) untuk mencegah spoilage perishable"
                    return adjusted_qty, moq_applied, packaging_applied, note
                else:
                    adjusted_qty = round_up_qty
            else:
                # Non-perishable standard: round up to next multiple
                adjusted_qty = math.ceil(adjusted_qty / packaging_multiple) * packaging_multiple

        note = "Sesuai kelipatan kemasan" if packaging_applied else "Sesuai kebutuhan rekomendasi"
        if moq_applied:
            note += f" (Disesuaikan ke MOQ {moq})"

        return adjusted_qty, moq_applied, packaging_applied, note
