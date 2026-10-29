from backend.src.services.telegram_service import TelegramService


def test_recommendation_card_is_short_and_operator_friendly():
    message = TelegramService.format_recommendation_message(
        store_name="Gerai Pilot Semarang 01",
        sku_name="Minyak Goreng Sawit 2L",
        current_stock=5,
        recommended_qty=48,
        confidence=0.82,
        reasoning=(
            "- Stok tersisa 5 pcs dan diperkirakan habis sebelum kiriman tiba.\n"
            "- Hari gajian dapat meningkatkan kebutuhan rumah tangga.\n"
            "- Jumlah 48 pcs cukup untuk menjaga pasokan beberapa hari."
        ),
        warnings=["Confidence moderat (60%-84%): Wajib verifikasi Kepala Toko."],
        daily_burn_rate=10,
        threshold=20,
        lead_time_days=2,
        packaging_multiple=12,
    )

    assert "💡 <b>Alasan Pengadaan:</b>" in message
    assert "🏪 <b>Toko:</b> Gerai Pilot Semarang 01" in message
    assert "📊 <b>Sisa Stok:</b> 5 Pcs (Kritis! Habis dlm ~12 jam)" in message
    assert "🎯 <b>Usulan Order:</b> 48 Pcs (4 kemasan @ 12 Pcs)" in message
    assert "📈 <b>Keyakinan AI:</b> 82%" in message
    assert "Keyakinan AI belum tinggi; mohon periksa sebelum menyetujui." in message
    assert "deterministik" not in message.lower()
    assert "Pareto" not in message
    assert "baseline" not in message.lower()


def test_fallback_card_remains_explicit_and_requires_review():
    message = TelegramService.format_recommendation_message(
        store_name="Toko 01",
        sku_name="Beras 5kg",
        current_stock=10,
        recommended_qty=30,
        confidence=0.60,
        reasoning="Perhitungan sementara berdasarkan stok dan waktu pengiriman.",
        is_fallback=True,
    )

    assert "AI sedang tidak tersedia" in message
    assert "wajib diperiksa" in message
    assert "💡 <b>Alasan Pengadaan:</b>" in message
