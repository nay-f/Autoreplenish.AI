"""DynamoDB Service for Single-Table Design.

Supports StoreMetadata, SKUProfile, WeatherCache, TelegramState, AuditLog, and FeedbackLog.
Includes in-memory simulation store for local testing & offline environments.
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from ..config import DYNAMODB_TABLE, logger, WEATHER_CACHE_TTL_HOURS
from ..models.schema import (
    StoreProfile,
    SKUProfile,
    WeatherContext,
    TelegramStateRecord,
    AuditLogRecord,
    FeedbackLogRecord,
)

class DynamoDBService:
    """DynamoDB Single Table Operations."""

    def __init__(self, table_name: Optional[str] = None, client: Optional[Any] = None):
        self.table_name = table_name or DYNAMODB_TABLE
        self.client = client
        # In-memory storage for offline / unit tests / fallback
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, pk: str, sk: str) -> str:
        return f"{pk}###{sk}"

    # ---------------------------------------------------------
    # 1. Store Profiles
    # ---------------------------------------------------------
    def put_store(self, store: StoreProfile) -> None:
        pk = f"STORE#{store.store_id}"
        sk = "PROFILE"
        item = store.to_dict()
        item["PK"] = pk
        item["SK"] = sk
        self._memory_store[self._get_key(pk, sk)] = item

    def get_store(self, store_id: str) -> Optional[StoreProfile]:
        pk = f"STORE#{store_id}"
        sk = "PROFILE"
        item = self._memory_store.get(self._get_key(pk, sk))
        if item:
            data = {k: v for k, v in item.items()}
            return StoreProfile(**data)
        return None

    def list_all_stores(self) -> List[StoreProfile]:
        stores = []
        for key, item in self._memory_store.items():
            if key.startswith("STORE#") and key.endswith("###PROFILE"):
                stores.append(StoreProfile(**item))
        return stores

    # ---------------------------------------------------------
    # 2. SKU Profiles
    # ---------------------------------------------------------
    def put_sku(self, sku: SKUProfile) -> None:
        pk = f"SKU#{sku.sku_id}"
        sk = "PROFILE"
        item = sku.to_dict()
        item["PK"] = pk
        item["SK"] = sk
        self._memory_store[self._get_key(pk, sk)] = item

    def get_sku(self, sku_id: str) -> Optional[SKUProfile]:
        pk = f"SKU#{sku_id}"
        sk = "PROFILE"
        item = self._memory_store.get(self._get_key(pk, sk))
        if item:
            return SKUProfile(**item)
        return None

    def list_all_skus(self) -> List[SKUProfile]:
        skus = []
        for key, item in self._memory_store.items():
            if key.startswith("SKU#") and key.endswith("###PROFILE"):
                skus.append(SKUProfile(**item))
        return skus

    # ---------------------------------------------------------
    # 3. Weather Cache
    # ---------------------------------------------------------
    def put_weather_cache(self, zone_id: str, weather: WeatherContext) -> None:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H")
        pk = f"ZONE#{zone_id}"
        sk = f"WEATHER#{date_str}#{hour_str}"

        ttl = int(time.time()) + (WEATHER_CACHE_TTL_HOURS * 3600)
        item = weather.to_dict()
        item.update({
            "PK": pk,
            "SK": sk,
            "ttl": ttl,
            "zone_id": zone_id,
            "cached_epoch": time.time()
        })
        self._memory_store[self._get_key(pk, sk)] = item

    def get_weather_cache(self, zone_id: str) -> Optional[Dict[str, Any]]:
        pk = f"ZONE#{zone_id}"
        matching = [
            v for k, v in self._memory_store.items()
            if k.startswith(f"{pk}###WEATHER#")
        ]
        if not matching:
            return None

        matching.sort(key=lambda x: x.get("cached_epoch", 0), reverse=True)
        latest = matching[0]

        if latest.get("ttl", 0) < time.time():
            return None

        return latest

    # ---------------------------------------------------------
    # 4. Telegram State Machine
    # ---------------------------------------------------------
    def put_telegram_state(self, state: TelegramStateRecord) -> None:
        pk = f"REQ#{state.request_id}"
        sk = "STATE"
        item = state.to_dict()
        item["PK"] = pk
        item["SK"] = sk
        self._memory_store[self._get_key(pk, sk)] = item

    def get_telegram_state(self, request_id: str) -> Optional[TelegramStateRecord]:
        pk = f"REQ#{request_id}"
        sk = "STATE"
        item = self._memory_store.get(self._get_key(pk, sk))
        if item:
            return TelegramStateRecord(**item)
        return None

    def update_telegram_state_status(
        self,
        request_id: str,
        status: str,
        final_qty: Optional[int] = None,
        rejection_reason: Optional[str] = None,
        sap_pr_id: Optional[str] = None,
        sap_error_message: Optional[str] = None
    ) -> Optional[TelegramStateRecord]:
        state = self.get_telegram_state(request_id)
        if not state:
            return None

        state.status = status
        if final_qty is not None:
            state.final_qty = final_qty
        if rejection_reason is not None:
            state.rejection_reason = rejection_reason
        if sap_pr_id is not None:
            state.sap_pr_id = sap_pr_id
        if sap_error_message is not None:
            state.sap_error_message = sap_error_message

        self.put_telegram_state(state)
        return state

    # ---------------------------------------------------------
    # 5. Audit Log Records
    # ---------------------------------------------------------
    def put_audit_log(self, log: AuditLogRecord) -> None:
        pk = f"AUDIT#{log.store_id}"
        sk = f"TS#{log.created_at}#SKU#{log.sku_id}"
        item = log.to_dict()
        item["PK"] = pk
        item["SK"] = sk
        self._memory_store[self._get_key(pk, sk)] = item

    def get_audit_log_by_request_id(self, request_id: str) -> Optional[AuditLogRecord]:
        for item in self._memory_store.values():
            if item.get("request_id") == request_id and "ai_recommended_qty" in item:
                return AuditLogRecord(**item)
        return None

    def list_audit_logs(
        self,
        store_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditLogRecord]:
        results = []
        for item in self._memory_store.values():
            if "ai_recommended_qty" not in item:
                continue
            if store_id and item.get("store_id") != store_id:
                continue
            if status and item.get("sap_pr_status") != status and item.get("human_action") != status:
                continue

            results.append(AuditLogRecord(**item))

        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[:limit]

    # ---------------------------------------------------------
    # 6. Feedback Log Records
    # ---------------------------------------------------------
    def put_feedback_log(self, feedback: FeedbackLogRecord) -> None:
        pk = f"FEEDBACK#{feedback.store_id}#{feedback.sku_id}"
        sk = f"TS#{feedback.created_at}"
        item = feedback.to_dict()
        item["PK"] = pk
        item["SK"] = sk
        self._memory_store[self._get_key(pk, sk)] = item

    def list_recent_feedback(self, store_id: str, sku_id: str, limit: int = 3) -> List[FeedbackLogRecord]:
        prefix = f"FEEDBACK#{store_id}#{sku_id}"
        matching = [
            v for k, v in self._memory_store.items()
            if k.startswith(f"{prefix}###TS#")
        ]
        matching.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        results = []
        for item in matching[:limit]:
            results.append(FeedbackLogRecord(**item))
        return results

    def list_all_feedbacks(self) -> List[FeedbackLogRecord]:
        results = []
        for item in self._memory_store.values():
            if "original_recommended_qty" in item and "action" in item:
                results.append(FeedbackLogRecord(**item))
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results
