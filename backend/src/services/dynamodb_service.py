"""DynamoDB Service for Single-Table Design (real AWS SDK implementation).

Implements PRD Section 13.3 and 14.5:
- StoreMetadata, SKUProfile, WeatherCache, TelegramState, AuditLog, FeedbackLog,
  and SapTransaction entities on a single table with PK/SK.
- Weather cache reads use a reverse-range query (ScanIndexForward=False, Limit=1)
  on the ZONE partition key, per PRD Section 11.4.
- TTL (6 hours) is written on every weather cache item per PRD Section 11.4.

The boto3 ``Table`` resource is injectable so that unit tests can run against a
moto-emulated DynamoDB endpoint instead of a live AWS account.
"""

import time
from dataclasses import fields as dataclass_fields
from decimal import Decimal
from typing import Dict, Any, List, Optional, Type, TypeVar

import boto3
from botocore.config import Config as BotoConfig

from ..config import logger, DYNAMODB_TABLE, AWS_REGION, WEATHER_CACHE_TTL_HOURS, APPROVAL_TIMEOUT_HOURS
from ..models.schema import (
    StoreProfile,
    SKUProfile,
    WeatherContext,
    TelegramStateRecord,
    AuditLogRecord,
    FeedbackLogRecord,
    SapTransactionRecord,
)

T = TypeVar("T")

# Keys written by the single-table access pattern that are not entity fields.
DYNAMO_ONLY_KEYS = {"GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "ttl", "cached_epoch"}


class DynamoDBService:
    """DynamoDB Single Table Operations backed by the real AWS SDK."""

    def __init__(
        self,
        table_name: Optional[str] = None,
        client: Optional[Any] = None,
        boto3_resource: Optional[Any] = None,
    ):
        """
        Args:
            table_name: Overrides config.DYNAMODB_TABLE.
            client: Pre-built boto3 ``Table`` resource (used by tests/moto).
            boto3_resource: Pre-built ``boto3.resource('dynamodb')`` (used by tests).
        """
        self.table_name = table_name or DYNAMODB_TABLE
        if client is not None:
            self.table = client
        else:
            resource = boto3_resource or boto3.resource(
                "dynamodb",
                region_name=AWS_REGION,
                config=BotoConfig(retries={"max_attempts": 5, "mode": "standard"}),
            )
            self.table = resource.Table(self.table_name)

    # ---------------------------------------------------------
    # Serialization helpers
    # ---------------------------------------------------------
    @staticmethod
    def _serialize(value: Any) -> Any:
        """Recursively convert a Python value into a DynamoDB-safe type.

        boto3's resource-level serializer refuses ``float`` ("Float types are not
        supported. Use Decimal types instead."), so every float is converted via
        its shortest repr to avoid binary artefacts (0.1 -> Decimal('0.1')).
        """
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, str, Decimal)):
            return value
        if isinstance(value, float):
            return Decimal(str(value))
        if isinstance(value, dict):
            return {k: DynamoDBService._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [DynamoDBService._serialize(v) for v in value]
        return str(value)

    @staticmethod
    def _deserialize(value: Any) -> Any:
        """Convert DynamoDB ``Decimal`` back to the narrowest Python numeric type.

        DynamoDB returns *every* number as a Decimal. Returning a float for an
        integral value would both corrupt integer semantics (quantity 30 -> 30.0)
        and break a subsequent write, since boto3 rejects floats outright.
        """
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, Decimal):
            if value == value.to_integral_value():
                return int(value)
            return float(value)
        if isinstance(value, dict):
            return {k: DynamoDBService._deserialize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [DynamoDBService._deserialize(v) for v in value]
        return value

    @classmethod
    def _clean(cls, entity: Any) -> Dict[str, Any]:
        """Flatten an entity into a DynamoDB-safe item.

        boto3's low-level serializer cannot encode ``None`` as an AttributeValue
        and raises an opaque exception, so null-valued fields are dropped.
        """
        raw = entity.to_dict() if hasattr(entity, "to_dict") else dict(entity)
        return {
            k: cls._serialize(v)
            for k, v in raw.items()
            if v is not None
        }

    @staticmethod
    def _hydrate(cls: Type[T], item: Optional[Dict[str, Any]]) -> Optional[T]:
        """Rebuild a dataclass from a raw DynamoDB item, dropping index/meta keys."""
        if not item:
            return None
        allowed = {f.name for f in dataclass_fields(cls)}
        data = {k: DynamoDBService._deserialize(v) for k, v in item.items() if k in allowed}
        return cls(**data)

    @staticmethod
    def _hydrate_many(cls: Type[T], items: List[Dict[str, Any]]) -> List[T]:
        allowed = {f.name for f in dataclass_fields(cls)}
        return [
            cls(**{k: DynamoDBService._deserialize(v) for k, v in item.items() if k in allowed})
            for item in items
        ]

    # ---------------------------------------------------------
    # 1. Store Profiles
    # ---------------------------------------------------------
    def put_store(self, store: StoreProfile) -> None:
        self.table.put_item(Item=self._clean(store))

    def get_store(self, store_id: str) -> Optional[StoreProfile]:
        resp = self.table.get_item(Key={"PK": f"STORE#{store_id}", "SK": "PROFILE"})
        return self._hydrate(StoreProfile, resp.get("Item"))

    def list_all_stores(self) -> List[StoreProfile]:
        resp = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "STORE"},
        )
        return self._hydrate_many(StoreProfile, resp.get("Items", []))

    # ---------------------------------------------------------
    # 2. SKU Profiles
    # ---------------------------------------------------------
    def put_sku(self, sku: SKUProfile) -> None:
        self.table.put_item(Item=self._clean(sku))

    def get_sku(self, sku_id: str) -> Optional[SKUProfile]:
        resp = self.table.get_item(Key={"PK": f"SKU#{sku_id}", "SK": "PROFILE"})
        return self._hydrate(SKUProfile, resp.get("Item"))

    def list_all_skus(self) -> List[SKUProfile]:
        resp = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "SKU"},
        )
        return self._hydrate_many(SKUProfile, resp.get("Items", []))

    # ---------------------------------------------------------
    # 3. Weather Cache (PRD Section 11.4)
    # ---------------------------------------------------------
    def put_weather_cache(self, zone_id: str, weather: WeatherContext) -> None:
        """Persist a weather snapshot with a 6-hour DynamoDB TTL.

        SK uses a sortable timestamp so that a reverse-range query returns the
        freshest entry without colliding with writes in the same clock hour.
        """
        now = time.time()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))
        item = self._clean(weather)
        item.update({
            "PK": f"ZONE#{zone_id}",
            "SK": f"WEATHER#{stamp}",
            "ttl": int(now + (WEATHER_CACHE_TTL_HOURS * 3600)),
            "zone_id": zone_id,
            "cached_epoch": Decimal(str(now)),
        })
        self.table.put_item(Item=item)

    def get_weather_cache(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent cache entry for a zone, or None if absent/expired."""
        resp = self.table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"ZONE#{zone_id}"},
            ScanIndexForward=False,  # descending by SK -> newest first
            Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None

        latest = items[0]
        if float(latest.get("ttl", 0)) < time.time():
            logger.info(f"Weather cache entry for zone {zone_id} has exceeded its DynamoDB TTL")
            return None
        # Decimals come back from DynamoDB; convert so callers can use plain floats.
        return self._deserialize(latest)

    # ---------------------------------------------------------
    # 4. Telegram State Machine
    # ---------------------------------------------------------
    def put_telegram_state(self, state: TelegramStateRecord) -> None:
        self.table.put_item(Item=self._clean(state))

    def get_telegram_state(self, request_id: str) -> Optional[TelegramStateRecord]:
        resp = self.table.get_item(Key={"PK": f"REQ#{request_id}", "SK": "STATE"})
        return self._hydrate(TelegramStateRecord, resp.get("Item"))

    def update_telegram_state_status(
        self,
        request_id: str,
        status: str,
        final_qty: Optional[int] = None,
        rejection_reason: Optional[str] = None,
        sap_pr_id: Optional[str] = None,
        sap_error_message: Optional[str] = None,
        awaiting_input: Optional[str] = None,
        telegram_message_id: Optional[str] = None,
    ) -> Optional[TelegramStateRecord]:
        """Atomic in-place state transition without a read-modify-write race."""
        set_parts = ["#st = :st"]
        names = {"#st": "status"}
        values: Dict[str, Any] = {":st": status}

        if final_qty is not None:
            set_parts.append("#fq = :fq")
            names["#fq"] = "final_qty"
            values[":fq"] = final_qty
        if rejection_reason is not None:
            set_parts.append("#rr = :rr")
            names["#rr"] = "rejection_reason"
            values[":rr"] = rejection_reason
        if sap_pr_id is not None:
            set_parts.append("#sid = :sid")
            names["#sid"] = "sap_pr_id"
            values[":sid"] = sap_pr_id
        if sap_error_message is not None:
            set_parts.append("#err = :err")
            names["#err"] = "sap_error_message"
            values[":err"] = sap_error_message
        if awaiting_input is not None:
            set_parts.append("#ai = :ai")
            names["#ai"] = "awaiting_input"
            values[":ai"] = awaiting_input
        if telegram_message_id is not None:
            set_parts.append("#mid = :mid")
            names["#mid"] = "telegram_message_id"
            values[":mid"] = telegram_message_id

        self.table.update_item(
            Key={"PK": f"REQ#{request_id}", "SK": "STATE"},
            UpdateExpression="SET " + ", ".join(set_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return self.get_telegram_state(request_id)

    # ---------------------------------------------------------
    # 5. Audit Log Records
    # ---------------------------------------------------------
    def put_audit_log(self, log: AuditLogRecord) -> None:
        self.table.put_item(Item=self._clean(log))

    def get_audit_log_by_request_id(self, request_id: str) -> Optional[AuditLogRecord]:
        """Resolve an audit record by request_id through the sparse GSI2."""
        resp = self.table.query(
            IndexName="GSI2",
            KeyConditionExpression="GSI2PK = :pk",
            ExpressionAttributeValues={":pk": f"AUDIT#{request_id}"},
            Limit=1,
        )
        items = resp.get("Items", [])
        return self._hydrate(AuditLogRecord, items[0]) if items else None

    def list_audit_logs(
        self,
        store_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditLogRecord]:
        """List audit logs newest-first.

        Scoped by store partition when a store_id is given, otherwise via GSI1
        so every store is covered. ``status`` matches either the SAP outcome or
        the human action (mirroring the original report-filter semantics).
        """
        if store_id:
            resp = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": f"AUDIT#{store_id}"},
                ScanIndexForward=False,
                Limit=max(limit * 5, 100),  # headroom for client-side status filter
            )
        else:
            resp = self.table.query(
                IndexName="GSI1",
                KeyConditionExpression="GSI1PK = :pk",
                ExpressionAttributeValues={":pk": "AUDIT"},
                ScanIndexForward=False,
                Limit=max(limit * 5, 100),
            )

        logs = self._hydrate_many(AuditLogRecord, resp.get("Items", []))
        if status:
            logs = [
                l for l in logs
                if l.sap_pr_status == status or l.human_action == status
            ]
        return logs[:limit]

    # ---------------------------------------------------------
    # 6. Feedback Log Records
    # ---------------------------------------------------------
    def put_feedback_log(self, feedback: FeedbackLogRecord) -> None:
        self.table.put_item(Item=self._clean(feedback))

    def list_recent_feedback(self, store_id: str, sku_id: str, limit: int = 3) -> List[FeedbackLogRecord]:
        resp = self.table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"FEEDBACK#{store_id}#{sku_id}"},
            ScanIndexForward=False,
            Limit=limit,
        )
        return self._hydrate_many(FeedbackLogRecord, resp.get("Items", []))

    def list_all_feedbacks(self) -> List[FeedbackLogRecord]:
        resp = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "FEEDBACK"},
            ScanIndexForward=False,
        )
        return self._hydrate_many(FeedbackLogRecord, resp.get("Items", []))

    # ---------------------------------------------------------
    # 7. SAP Transaction Ledger
    #    Persisted for BOTH modes so that idempotency survives
    #    Lambda cold starts (PRD Section 14.2 - "Cek status sebelum POST").
    # ---------------------------------------------------------
    def get_sap_transaction(self, request_id: str) -> Optional[SapTransactionRecord]:
        resp = self.table.get_item(Key={"PK": f"SAPTRANS#{request_id}", "SK": "TRANSACTION"})
        return self._hydrate(SapTransactionRecord, resp.get("Item"))

    def put_sap_transaction(self, txn: SapTransactionRecord) -> None:
        self.table.put_item(Item=self._clean(txn))

    def list_sap_transactions(self, limit: int = 50) -> List[SapTransactionRecord]:
        resp = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "SAPTRANS"},
            ScanIndexForward=False,
            Limit=limit,
        )
        return self._hydrate_many(SapTransactionRecord, resp.get("Items", []))

    # ---------------------------------------------------------
    # 8. Atomic counters
    #    Used for SAP Purchase Requisition numbering so both LIVE and
    #    PERSISTENT_SANDBOX modes emit monotonic, collision-free numbers
    #    without a read-modify-write race.
    # ---------------------------------------------------------
    def next_sequence(self, counter_name: str, initial_value: int = 0) -> int:
        """Atomically create-or-increment a named counter and return its new value."""
        resp = self.table.update_item(
            Key={"PK": f"COUNTER#{counter_name}", "SK": "VALUE"},
            UpdateExpression="ADD #seq :inc SET #upd = :now, #meta = :meta",
            ExpressionAttributeNames={
                "#seq": "seq",
                "#upd": "updated_at_epoch",
                "#meta": "entity",
            },
            ExpressionAttributeValues={
                ":inc": 1,
                ":now": Decimal(str(time.time())),
                ":meta": f"COUNTER#{counter_name}",
            },
            ReturnValues="UPDATED_NEW",
        )
        return int(resp["Attributes"]["seq"])

    def next_sap_pr_sequence(self) -> int:
        """Next SAP Purchase Requisition sequence number."""
        return self.next_sequence("SAP_PR")

    # ---------------------------------------------------------
    # 9. Chat -> pending request pointers
    #    Telegram only sends the chat_id on a free-text reply, so a pointer is
    #    needed to know which request an EDIT / REJECT answer belongs to.
    #    A webhook Lambda is stateless, so this lives in DynamoDB, not memory.
    # ---------------------------------------------------------
    def set_chat_pending_request(self, chat_id: str, request_id: str) -> None:
        item: Dict[str, Any] = {
            "PK": f"CHAT#{chat_id}",
            "SK": "PENDING",
            "request_id": request_id,
            "updated_at_epoch": Decimal(str(time.time())),
            "GSI1PK": "CHATPENDING",
            "GSI1SK": str(chat_id),
            "ttl": int(time.time() + (APPROVAL_TIMEOUT_HOURS * 3600)),
        }
        self.table.put_item(Item=item)

    def get_chat_pending_request(self, chat_id: str) -> Optional[str]:
        resp = self.table.get_item(Key={"PK": f"CHAT#{chat_id}", "SK": "PENDING"})
        item = resp.get("Item")
        if not item:
            return None
        if float(item.get("ttl", 0)) < time.time():
            return None
        request_id = item.get("request_id")
        return str(request_id) if request_id else None

    def clear_chat_pending_request(self, chat_id: str) -> None:
        self.table.delete_item(Key={"PK": f"CHAT#{chat_id}", "SK": "PENDING"})
