"""Calendar & Promo Service.

Determines weekday/weekend, Indonesian public holidays, payday cycles, and active promotion multipliers.
"""

from datetime import date
from typing import Optional
from ..models.schema import CalendarContext, PromoContext

# Sample Indonesian Public Holidays for reference
INDONESIAN_HOLIDAYS = {
    "2026-01-01": "Tahun Baru Masehi",
    "2026-03-20": "Hari Raya Idul Fitri",
    "2026-03-21": "Hari Raya Idul Fitri",
    "2026-05-01": "Hari Buruh Internasional",
    "2026-05-28": "Hari Raya Waisak",
    "2026-08-17": "Hari Kemerdekaan RI",
    "2026-12-25": "Hari Raya Natal",
}

# Active promo catalog mapping by SKU and date
ACTIVE_PROMOS = {
    "SKU-10023": {  # Roti Manis Cokelat
        "promo_type": "JSM",
        "promo_name": "Promo JSM Weekend Manis",
        "multiplier_factor": 1.4,
        "active_days": [4, 5, 6]  # Friday, Saturday, Sunday
    },
    "SKU-10045": {  # Minuman Isotonik 500ml
        "promo_type": "Buy 1 Get 1",
        "promo_name": "Beli 1 Gratis 1 Segar",
        "multiplier_factor": 1.8,
        "active_days": [0, 1, 2, 3, 4, 5, 6]
    },
    "SKU-10088": {  # Sabun Cuci Piring
        "promo_type": "Payday Sale",
        "promo_name": "Pesta Gajian Rumah Bersih",
        "multiplier_factor": 1.5,
        "active_days": [0, 1, 2, 3, 4, 5, 6]
    }
}

class CalendarPromoService:
    """Evaluates time cycles, holidays, and promo factors."""

    def get_calendar_context(self, target_date: Optional[date] = None) -> CalendarContext:
        """Evaluate day type, public holiday, and payday status."""
        current_date = target_date or date.today()
        date_str = current_date.strftime("%Y-%m-%d")
        weekday_idx = current_date.weekday()  # 0: Mon, 4: Fri, 5: Sat, 6: Sun

        day_type = "Weekend" if weekday_idx in (5, 6) else "Weekday"
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_of_week = day_names[weekday_idx]

        # Holiday check
        is_holiday = date_str in INDONESIAN_HOLIDAYS
        holiday_name = INDONESIAN_HOLIDAYS.get(date_str)

        # Payday window check (typically 25th through end of month, or 1st-2nd)
        day_of_month = current_date.day
        is_payday = (day_of_month >= 25) or (day_of_month <= 2)

        return CalendarContext(
            day_type=day_type,
            day_of_week=day_of_week,
            is_public_holiday=is_holiday,
            holiday_name=holiday_name,
            is_payday=is_payday
        )

    def get_promo_context(
        self,
        sku_id: str,
        target_date: Optional[date] = None,
        store: Optional[Any] = None
    ) -> PromoContext:
        """Evaluate whether promo or local event is active for given SKU on target date."""
        current_date = target_date or date.today()
        date_str = current_date.strftime("%Y-%m-%d")
        weekday_idx = current_date.weekday()

        # 1. Check store-specific custom promos if available
        if store and hasattr(store, "promos") and store.promos:
            for promo in store.promos:
                target_skus = getattr(promo, "target_sku_ids", []) or []
                if not target_skus or sku_id in target_skus:
                    start = getattr(promo, "start_date", "")
                    end = getattr(promo, "end_date", "")
                    if (not start or start <= date_str) and (not end or date_str <= end):
                        return PromoContext(
                            is_active=True,
                            promo_type=getattr(promo, "promo_type", "Custom Promo"),
                            promo_name=getattr(promo, "promo_name", "Promo Toko"),
                            multiplier_factor=float(getattr(promo, "multiplier_factor", 1.3))
                        )

        # 2. Check store-specific local community events
        if store and hasattr(store, "local_events") and store.local_events:
            for ev in store.local_events:
                ev_date = getattr(ev, "event_date", "")
                if ev_date == date_str:
                    return PromoContext(
                        is_active=True,
                        promo_type="Local Event",
                        promo_name=getattr(ev, "event_name", "Event Lokal"),
                        multiplier_factor=float(getattr(ev, "impact_multiplier", 1.2))
                    )

        # 3. Fallback to default catalog
        promo_data = ACTIVE_PROMOS.get(sku_id)
        if not promo_data:
            return PromoContext(is_active=False)

        if weekday_idx in promo_data.get("active_days", []):
            return PromoContext(
                is_active=True,
                promo_type=promo_data["promo_type"],
                promo_name=promo_data["promo_name"],
                multiplier_factor=promo_data["multiplier_factor"]
            )

        return PromoContext(is_active=False)
