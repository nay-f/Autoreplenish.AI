"""Master-data loader tests: generic multi-store seed fixtures + schema validation."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from conftest import moto_dynamo_table, TEST_TABLE_NAME
from src.data.master_data_loader import (
    MasterDataError,
    get_seed_stock_for_store,
    load_seed_skus,
    load_seed_stock_levels,
    load_seed_stores,
)
from src.services.dynamodb_service import DynamoDBService


def _valid_store(**overrides):
    record = {
        "store_id": "STR-T-01", "store_name": "Toko Uji", "area_type": "Umum", "zone": "ZONA_UJI",
        "address": "", "latitude": -6.2, "longitude": 106.8, "sap_plant": "1000",
        "storage_location": "STR-T-01", "telegram_chat_id": "", "active": True,
    }
    record.update(overrides)
    return record


def _valid_sku(**overrides):
    record = {
        "sku_id": "SKU-T-01", "sku_name": "Barang Uji", "category": "Non-Perishable",
        "weather_sensitive": False, "moq": 1, "packaging_multiple": 1, "base_unit": "PCS",
        "default_lead_time_days": 1, "vendor_id": "VEN-T", "price_idr": 1000.0,
        "shelf_life_days": 30, "is_fragile": False,
    }
    record.update(overrides)
    return record


class TestSeedFixtures(unittest.TestCase):

    def test_two_generic_stores_are_defined(self):
        stores = {s.store_id: s for s in load_seed_stores()}
        self.assertEqual(set(stores), {"STR-COMMERCIAL-01", "STR-RESIDENTIAL-01"})
        self.assertEqual(stores["STR-COMMERCIAL-01"].area_type, "Komersial / Perkantoran")
        self.assertEqual(stores["STR-RESIDENTIAL-01"].area_type, "Pemukiman Warga")
        self.assertAlmostEqual(stores["STR-COMMERCIAL-01"].latitude, -6.2088, places=4)
        self.assertAlmostEqual(stores["STR-RESIDENTIAL-01"].longitude, 110.4166, places=4)

    def test_four_generic_skus_are_defined(self):
        skus = {s.sku_id: s for s in load_seed_skus()}
        self.assertEqual(set(skus), {"SKU-FMCG-001", "SKU-FMCG-002", "SKU-FMCG-003", "SKU-FMCG-004"})
        self.assertEqual((skus["SKU-FMCG-001"].category, skus["SKU-FMCG-001"].shelf_life_days,
                          skus["SKU-FMCG-001"].moq), ("Perishable", 3, 12))
        self.assertEqual((skus["SKU-FMCG-002"].category, skus["SKU-FMCG-002"].moq), ("Non-Perishable", 5))
        self.assertEqual((skus["SKU-FMCG-003"].category, skus["SKU-FMCG-003"].moq), ("Non-Perishable", 6))
        self.assertTrue(skus["SKU-FMCG-004"].weather_sensitive)
        self.assertEqual(skus["SKU-FMCG-004"].moq, 24)

    def test_opening_stock_references_only_catalogued_skus(self):
        known = {s.sku_id for s in load_seed_skus()}
        levels = load_seed_stock_levels()
        self.assertEqual(set(levels), {"STR-COMMERCIAL-01", "STR-RESIDENTIAL-01"})
        for store_stock in levels.values():
            self.assertTrue(set(store_stock) <= known)
        self.assertEqual(get_seed_stock_for_store("STR-UNKNOWN"), {})

    def test_loader_returns_fresh_objects_each_call(self):
        first = load_seed_stores()
        first[0].telegram_chat_id = "mutated"
        self.assertEqual(load_seed_stores()[0].telegram_chat_id, "")

    def test_store_coordinates_survive_a_dynamodb_round_trip(self):
        with moto_dynamo_table() as table:
            db = DynamoDBService(table_name=TEST_TABLE_NAME, client=table)
            for store in load_seed_stores():
                db.put_store(store)
            fetched = db.get_store("STR-RESIDENTIAL-01")
        self.assertAlmostEqual(fetched.latitude, -6.9666, places=4)
        self.assertAlmostEqual(fetched.longitude, 110.4166, places=4)


class TestSeedValidation(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _write(self, name, document):
        path = self.dir / name
        path.write_text(json.dumps(document) if not isinstance(document, str) else document, encoding="utf-8")
        return path

    def test_missing_file_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_stores(self.dir / "absent.json")

    def test_invalid_json_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_stores(self._write("bad.json", "{not json"))

    def test_missing_root_key_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_stores(self._write("s.json", {"wrong": []}))

    def test_valid_custom_store_loads(self):
        stores = load_seed_stores(self._write("s.json", {"stores": [_valid_store()]}))
        self.assertEqual(stores[0].store_id, "STR-T-01")

    def test_duplicate_store_id_raises(self):
        path = self._write("s.json", {"stores": [_valid_store(), _valid_store()]})
        with self.assertRaises(MasterDataError):
            load_seed_stores(path)

    def test_out_of_range_latitude_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_stores(self._write("s.json", {"stores": [_valid_store(latitude=95.0)]}))

    def test_latitude_without_longitude_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_stores(self._write("s.json", {"stores": [_valid_store(longitude=None)]}))

    def test_store_without_coordinates_is_allowed(self):
        stores = load_seed_stores(self._write(
            "s.json", {"stores": [_valid_store(latitude=None, longitude=None)]}))
        self.assertIsNone(stores[0].latitude)
        self.assertIsNone(stores[0].longitude)

    def test_wrong_type_active_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_stores(self._write("s.json", {"stores": [_valid_store(active="yes")]}))

    def test_invalid_sku_category_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_skus(self._write("k.json", {"skus": [_valid_sku(category="Frozen")]}))

    def test_sku_moq_below_one_raises(self):
        with self.assertRaises(MasterDataError):
            load_seed_skus(self._write("k.json", {"skus": [_valid_sku(moq=0)]}))

    def test_boolean_is_not_accepted_as_integer(self):
        with self.assertRaises(MasterDataError):
            load_seed_skus(self._write("k.json", {"skus": [_valid_sku(moq=True)]}))

    def test_stock_for_unknown_sku_raises(self):
        store = _valid_store()
        store["opening_stock"] = {"SKU-GHOST": {
            "physical_stock": 1, "threshold": 2, "average_daily_burn_rate": 1, "lead_time_days": 1}}
        stores_path = self._write("s.json", {"stores": [store]})
        skus_path = self._write("k.json", {"skus": [_valid_sku()]})
        with self.assertRaises(MasterDataError):
            load_seed_stock_levels(stores_path, skus_path)


if __name__ == "__main__":
    unittest.main()
