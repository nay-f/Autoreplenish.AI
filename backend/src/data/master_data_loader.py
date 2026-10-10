"""Master-data loader for the generic (multi-store) seed fixtures.

Reads ``seed_stores.json`` and ``seed_skus.json`` from this directory and turns
them into the typed ``StoreProfile`` / ``SKUProfile`` models. It is the single
source of master data for the scheduled evaluation handler, the orchestrator,
the dashboard API and the demo seeding script, so no store or SKU is hardcoded
in Python code.

The files are external input, so every record is schema-validated and a
``MasterDataError`` with a precise location is raised for any violation
(never swallowed, never silently defaulted).
"""

import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Tuple, Union

from ..config import logger
from ..models.schema import SKUProfile, StoreProfile

SEED_DIR = Path(__file__).resolve().parent
SEED_STORES_PATH = SEED_DIR / "seed_stores.json"
SEED_SKUS_PATH = SEED_DIR / "seed_skus.json"

VALID_SKU_CATEGORIES = ("Perishable", "Non-Perishable")

# Opening stock snapshot of one store: {sku_id: {metric: value}}.
StockLevels = Dict[str, Dict[str, Union[int, float]]]

_STOCK_FIELDS = ("physical_stock", "threshold", "average_daily_burn_rate", "lead_time_days")
_OPTIONAL_STOCK_FIELDS = ("open_pr_qty",)

PathLike = Union[str, Path]


class MasterDataError(ValueError):
    """Raised when a master-data fixture is missing, malformed, or inconsistent."""


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def _read_json_list(path: Path, root_key: str) -> List[Mapping[str, object]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError as exc:
        logger.error(f"Master data file not found: {path}")
        raise MasterDataError(f"Master data file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        logger.error(f"Master data file {path} is not valid JSON: {exc}")
        raise MasterDataError(f"{path.name} is not valid JSON: {exc}") from exc

    records = document.get(root_key) if isinstance(document, dict) else None
    if not isinstance(records, list):
        raise MasterDataError(f"{path.name}: top-level key '{root_key}' must be a list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise MasterDataError(f"{path.name}: {root_key}[{index}] must be an object")
    return records


def _require_str(record: Mapping[str, object], key: str, where: str, allow_empty: bool = False) -> str:
    value = record.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise MasterDataError(f"{where}: '{key}' must be a non-empty string")
    return value.strip() if not allow_empty else value


def _require_bool(record: Mapping[str, object], key: str, where: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise MasterDataError(f"{where}: '{key}' must be a boolean")
    return value


def _require_int(record: Mapping[str, object], key: str, where: str, minimum: int) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MasterDataError(f"{where}: '{key}' must be an integer >= {minimum}")
    return value


def _require_number(record: Mapping[str, object], key: str, where: str, minimum: float) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise MasterDataError(f"{where}: '{key}' must be a number >= {minimum}")
    return float(value)


def _optional_coordinate(
    record: Mapping[str, object], key: str, where: str, limit: float
) -> Optional[float]:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MasterDataError(f"{where}: '{key}' must be a number or null")
    if not -limit <= float(value) <= limit:
        raise MasterDataError(f"{where}: '{key}' must be within [-{limit}, {limit}]")
    return float(value)


def _parse_stock(store_id: str, raw_stock: object) -> StockLevels:
    where = f"store '{store_id}' opening_stock"
    if raw_stock is None:
        return {}
    if not isinstance(raw_stock, dict):
        raise MasterDataError(f"{where} must be an object keyed by sku_id")

    stock: StockLevels = {}
    for sku_id, metrics in raw_stock.items():
        entry_where = f"{where}['{sku_id}']"
        if not isinstance(metrics, dict):
            raise MasterDataError(f"{entry_where} must be an object")
        entry: Dict[str, Union[int, float]] = {}
        for field_name in _STOCK_FIELDS:
            value = metrics.get(field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise MasterDataError(f"{entry_where}: '{field_name}' must be a number >= 0")
            entry[field_name] = value
        for field_name in _OPTIONAL_STOCK_FIELDS:
            value = metrics.get(field_name, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise MasterDataError(f"{entry_where}: '{field_name}' must be a number >= 0")
            entry[field_name] = value
        stock[sku_id] = entry
    return stock


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _parse_stores(path: Path) -> List[Tuple[StoreProfile, StockLevels]]:
    """Return ``[(StoreProfile, StockLevels), ...]`` after validating each record."""
    parsed: List[Tuple[StoreProfile, StockLevels]] = []
    seen_ids: Set[str] = set()
    for index, record in enumerate(_read_json_list(path, "stores")):
        where = f"{path.name}: stores[{index}]"
        store_id = _require_str(record, "store_id", where)
        if store_id in seen_ids:
            raise MasterDataError(f"{where}: duplicate store_id '{store_id}'")
        seen_ids.add(store_id)

        latitude = _optional_coordinate(record, "latitude", where, 90.0)
        longitude = _optional_coordinate(record, "longitude", where, 180.0)
        if (latitude is None) != (longitude is None):
            raise MasterDataError(f"{where}: 'latitude' and 'longitude' must be provided together")

        store = StoreProfile(
            store_id=store_id,
            store_name=_require_str(record, "store_name", where),
            area_type=_require_str(record, "area_type", where),
            zone=_require_str(record, "zone", where),
            address=_require_str(record, "address", where, allow_empty=True),
            sap_plant=_require_str(record, "sap_plant", where),
            storage_location=_require_str(record, "storage_location", where),
            telegram_chat_id=_require_str(record, "telegram_chat_id", where, allow_empty=True),
            active=_require_bool(record, "active", where),
            latitude=latitude,
            longitude=longitude,
        )
        parsed.append((store, _parse_stock(store_id, record.get("opening_stock"))))
    return parsed


def load_seed_stores(path: Optional[PathLike] = None) -> List[StoreProfile]:
    """Load and validate the store master data (``seed_stores.json``)."""
    return [store for store, _ in _parse_stores(Path(path) if path else SEED_STORES_PATH)]


def load_seed_skus(path: Optional[PathLike] = None) -> List[SKUProfile]:
    """Load and validate the SKU master data (``seed_skus.json``)."""
    file_path = Path(path) if path else SEED_SKUS_PATH
    skus: List[SKUProfile] = []
    seen_ids: Set[str] = set()
    for index, record in enumerate(_read_json_list(file_path, "skus")):
        where = f"{file_path.name}: skus[{index}]"
        sku_id = _require_str(record, "sku_id", where)
        if sku_id in seen_ids:
            raise MasterDataError(f"{where}: duplicate sku_id '{sku_id}'")
        seen_ids.add(sku_id)

        category = _require_str(record, "category", where)
        if category not in VALID_SKU_CATEGORIES:
            raise MasterDataError(f"{where}: 'category' must be one of {VALID_SKU_CATEGORIES}")

        skus.append(SKUProfile(
            sku_id=sku_id,
            sku_name=_require_str(record, "sku_name", where),
            category=category,
            weather_sensitive=_require_bool(record, "weather_sensitive", where),
            moq=_require_int(record, "moq", where, minimum=1),
            packaging_multiple=_require_int(record, "packaging_multiple", where, minimum=1),
            base_unit=_require_str(record, "base_unit", where),
            default_lead_time_days=_require_int(record, "default_lead_time_days", where, minimum=0),
            vendor_id=_require_str(record, "vendor_id", where),
            price_idr=_require_number(record, "price_idr", where, minimum=0),
            shelf_life_days=_require_int(record, "shelf_life_days", where, minimum=1),
            is_fragile=_require_bool(record, "is_fragile", where),
        ))
    return skus


def load_seed_stock_levels(
    stores_path: Optional[PathLike] = None,
    skus_path: Optional[PathLike] = None,
) -> Dict[str, StockLevels]:
    """Load the opening stock snapshot as ``{store_id: {sku_id: metrics}}``.

    Every referenced SKU must exist in the SKU catalogue, otherwise a
    ``MasterDataError`` is raised (prevents dangling references in the fixtures).
    """
    known_skus = {sku.sku_id for sku in load_seed_skus(skus_path)}
    result: Dict[str, StockLevels] = {}
    for store, stock in _parse_stores(Path(stores_path) if stores_path else SEED_STORES_PATH):
        unknown = sorted(set(stock) - known_skus)
        if unknown:
            raise MasterDataError(
                f"store '{store.store_id}' opening_stock references unknown SKU(s): {unknown}"
            )
        result[store.store_id] = stock
    return result


def get_seed_stock_for_store(store_id: str) -> StockLevels:
    """Opening stock for one store; ``{}`` when the store has no seeded snapshot."""
    return load_seed_stock_levels().get(store_id, {})
