from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.models.schema import StoreProfile, SKUItem

def run_test():
    print("Inisialisasi DynamoDB Service...")
    db = DynamoDBService()

    # 1. Simpan profil toko
    sample_store = StoreProfile(
        store_id="STR-TEST-001",
        store_name="Minimarket Percontohan USM",
        area_type="Komersial / Perkantoran",
        zone="ZONE-SEMARANG-01",
        latitude=-6.9666,
        longitude=110.4166,
        telegram_chat_id="123456789"
    )
    db.save_store(sample_store)
    print("Berhasil menyimpan StoreProfile ke DynamoDB!")

    # 2. Ambil kembali toko
    retrieved_store = db.get_store("STR-TEST-001")
    assert retrieved_store is not None
    assert retrieved_store.store_name == "Minimarket Percontohan USM"
    print(f"Berhasil membaca data toko: {retrieved_store.store_name} (Lat: {retrieved_store.latitude})")

    # 3. Simpan 1 SKU
    sample_sku = SKUItem(
        sku_id="SKU-ROTI-01",
        sku_name="Roti Manis Cokelat 100g",
        category="Perishable",
        physical_stock=10,
        threshold=25,
        average_daily_burn_rate=20.5,
        moq=12,
        packaging_multiple=12,
        is_perishable=True
    )
    db.save_sku(sample_store.store_id, sample_sku)
    print("Berhasil menyimpan SKUItem!")

    # 4. Baca daftar SKU
    skus = db.get_skus_for_store(sample_store.store_id)
    assert len(skus) >= 1
    print(f"Berhasil mengambil SKU: {skus[0].sku_name} (Stok: {skus[0].physical_stock})")
    print("\nSeluruh pengujian DynamoDB Service BERHASIL!")

if __name__ == "__main__":
    run_test()