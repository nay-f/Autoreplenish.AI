import math
from backend.src.models.schema import SKUItem

class MOQPackagingService:
    @staticmethod
    def adjust_quantity(sku: SKUItem, ai_qty: int, risk_level: str = "medium") -> dict:
        """
        Menyesuaikan kuota order AI terhadap aturan MOQ dan packaging multiple:
        - Non-Perishable: Dibulatkan ke atas (round up) ke kelipatan kardus terdekat.
        - Perishable + Risiko Tinggi (Cuaca buruk/weekend sepi): Dibulatkan konservatif ke bawah
          untuk menghindari overstock/spoilage.
        """
        moq = max(sku.moq, 1)
        multiple = max(sku.packaging_multiple, 1)
        
        # Jika AI merekomendasikan 0, tidak perlu order
        if ai_qty <= 0:
            return {
                "final_qty": 0,
                "moq_applied": False,
                "packaging_multiple_applied": False,
                "note": "AI merekomendasikan tidak ada order saat ini"
            }

        # Evaluasi terhadap MOQ minimal
        base_qty = max(ai_qty, moq)
        moq_applied = (ai_qty < moq)

        # Penyesuaian kelipatan kemasan
        if sku.is_perishable and risk_level == "high":
            # Pembulatan konservatif ke bawah untuk barang mudah rusak saat situasi berisiko
            batches = math.floor(base_qty / multiple)
            final_qty = max(batches * multiple, moq)
            note = f"Disesuaikan konservatif ke {final_qty} unit untuk menekan risiko kedaluwarsa"
        else:
            # Pembulatan ke atas (round up) standar logistik
            batches = math.ceil(base_qty / multiple)
            final_qty = batches * multiple
            note = f"Dibulatkan ke atas mengikuti kelipatan kemasan ({multiple} unit/dus)"

        return {
            "final_qty": final_qty,
            "moq_applied": moq_applied,
            "packaging_multiple_applied": (final_qty != ai_qty),
            "note": note
        }