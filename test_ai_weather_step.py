from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.services.weather_service import WeatherService
from backend.src.services.bedrock_service import BedrockReasoningService
from backend.src.services.moq_packaging_service import MOQPackagingService

def run_integration_test():
    print("=== PENGUJIAN INTEGRASI CUACA & PENALARAN BEDROCK ===")
    
    db = DynamoDBService()
    weather_svc = WeatherService(db)
    ai_svc = BedrockReasoningService()

    # 1. Ambil data toko dari DynamoDB
    store = db.get_store("STR-TEST-001")
    if not store:
        print("Toko STR-TEST-001 tidak ditemukan, jalankan test_db_step.py terlebih dahulu.")
        return

    print(f"\n[1] Toko Ditemukan: {store.store_name} ({store.area_type})")
    print(f"    Koordinat GPS: {store.latitude}, {store.longitude}")

    # 2. Ambil data SKU
    skus = db.get_skus_for_store(store.store_id)
    target_sku = skus[0]
    print(f"\n[2] Target Evaluasi: {target_sku.sku_name}")
    print(f"    Stok Saat Ini: {target_sku.physical_stock} Pcs | Threshold: {target_sku.threshold} Pcs")

    # 3. Tarik Cuaca Riil
    print("\n[3] Mengambil Sinyal Cuaca Riil...")
    weather = weather_svc.get_weather_for_store(store)
    print(f"    Kondisi: {weather.get('condition')} | Suhu: {weather.get('temperature_c')}°C")
    print(f"    Sumber Data: {'DynamoDB Cache' if weather.get('is_cached') else 'OpenWeatherMap Live'}")

    # 4. Susun Konteks Kalender
    calendar_context = {
        "day_name": "Sabtu",
        "is_weekend": True,
        "is_payday": False,
        "is_holiday": False
    }

    # 5. Jalankan Penalaran AI Bedrock
    print(f"\n[4] Mengirim Konteks ke AWS Bedrock ({ai_svc.model_id})...")
    recommendation = ai_svc.generate_recommendation(
        store=store,
        sku=target_sku,
        weather=weather,
        calendar_context=calendar_context
    )

    print("\n--- HASIL PENALARAN CLAUDE SONNET ---")
    print(f"Status Mode       : {'[FALLBACK RULE]' if recommendation.is_fallback else '[BEDROCK LIVE]'}")
    print(f"Rekomendasi AI    : {recommendation.recommended_qty} Unit (Normal: {recommendation.normal_qty})")
    print(f"Confidence Score  : {recommendation.confidence_score * 100:.1f}%")
    print(f"Level Risiko      : {recommendation.risk_level.upper()}")
    print(f"Narasi Penalaran  :\n\"{recommendation.reasoning_narrative}\"")
    if recommendation.warnings:
        print(f"Peringatan        : {', '.join(recommendation.warnings)}")

    # 6. Terapkan Aturan MOQ & Kemasan
    print("\n[5] Menerapkan Aturan Kemasan Distributor...")
    moq_result = MOQPackagingService.adjust_quantity(
        sku=target_sku,
        ai_qty=recommendation.recommended_qty,
        risk_level=recommendation.risk_level
    )
    print(f"    Hasil Akhir Order : {moq_result['final_qty']} Pcs")
    print(f"    Catatan Penyesuaian: {moq_result['note']}")
    print("\n=== UJI INTEGRASI SELESAI DENGAN SUKSES ===")

if __name__ == "__main__":
    run_integration_test()