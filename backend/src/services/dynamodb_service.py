import time
import logging
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import backend.src.config as config
from backend.src.models.schema import SKUItem, StoreProfile, TelegramApprovalState

logger = logging.getLogger("autoreplenish.dynamodb")

# Aturan State Machine Resmi (P1 #14)
VALID_STATE_TRANSITIONS = {
    "PENDING_APPROVAL": {"APPROVED", "EDIT_REQUESTED", "REJECTED", "SAP_SUBMITTING", "TIMEOUT"},
    "EDIT_REQUESTED": {"APPROVED", "EDITED", "REJECTED", "SAP_SUBMITTING", "TIMEOUT"},
    "APPROVED": {"SAP_SUBMITTING", "SAP_SUBMITTED", "SAP_FAILED"},
    "SAP_SUBMITTING": {"SAP_SUBMITTED", "SAP_FAILED", "EDITED"},
    "SAP_FAILED": {"SAP_SUBMITTING", "SAP_SUBMITTED"},
}


def _serialize_decimals(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _serialize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_decimals(i) for i in obj]
    return obj


def _deserialize_decimals(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: _deserialize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deserialize_decimals(i) for i in obj]
    return obj


class DynamoDBService:

    def __init__(self):
        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        )
        self.table = self.dynamodb.Table(config.DYNAMODB_TABLE)

    # =================================================================
    # 1. STORE PROFILE & SKU CRUD
    # =================================================================
    def save_store(self, store: StoreProfile):
        item = store.model_dump()
        item["PK"] = f"STORE#{store.store_id}"
        item["SK"] = "PROFILE"
        self.table.put_item(Item=_serialize_decimals(item))
        return store

    def get_store(self, store_id: str):
        response = self.table.get_item(
            Key={"PK": f"STORE#{store_id}", "SK": "PROFILE"}
        )
        if "Item" in response:
            data = _deserialize_decimals(response["Item"])
            return StoreProfile(**data)
        return None

    def list_stores(self) -> list[StoreProfile]:
        response = self.table.scan(
            FilterExpression=Attr("SK").eq("PROFILE")
        )
        items = _deserialize_decimals(response.get("Items", []))
        return [StoreProfile(**item) for item in items if item.get("PK", "").startswith("STORE#")]

    def save_sku(self, store_id: str, sku: SKUItem):
        item = sku.model_dump()
        item["PK"] = f"STORE#{store_id}"
        item["SK"] = f"SKU#{sku.sku_id}"
        self.table.put_item(Item=_serialize_decimals(item))
        return sku

    def get_skus_for_store(self, store_id: str) -> list[SKUItem]:
        response = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"STORE#{store_id}")
            & Key("SK").begins_with("SKU#")
        )
        items = _deserialize_decimals(response.get("Items", []))
        return [SKUItem(**item) for item in items]

    def delete_sku(self, store_id: str, sku_id: str):
        self.table.delete_item(
            Key={"PK": f"STORE#{store_id}", "SK": f"SKU#{sku_id}"}
        )

    # =================================================================
    # 2. WEATHER CACHE (TTL RESMI & METADATA SUMBER)
    # =================================================================
    def save_weather_cache(self, cache_key: str, weather_data: dict, ttl_timestamp: int):
        item = {
            "PK": f"ZONE#{cache_key}",
            "SK": "WEATHER#LATEST",
            "ttl": ttl_timestamp,
            "expires_at_epoch": ttl_timestamp,
            **weather_data,
        }
        self.table.put_item(Item=_serialize_decimals(item))

    def get_weather_cache(self, cache_key: str):
        response = self.table.get_item(
            Key={"PK": f"ZONE#{cache_key}", "SK": "WEATHER#LATEST"}
        )
        if "Item" in response:
            return _deserialize_decimals(response["Item"])
        return None

    # =================================================================
    # 3. PERSISTENT TELEGRAM SESSION (PENGGANTI RAM DICT - P1 #9)
    # =================================================================
    def save_telegram_session(self, chat_id: str, session_data: dict, ttl_seconds: int = 3600):
        now = int(time.time())
        item = {
            "PK": f"TG_SESSION#{chat_id}",
            "SK": "STATE",
            "chat_id": str(chat_id),
            "session_data": session_data,
            "updated_at": now,
            "ttl": now + ttl_seconds,
        }
        self.table.put_item(Item=_serialize_decimals(item))

    def get_telegram_session(self, chat_id: str) -> dict | None:
        response = self.table.get_item(
            Key={"PK": f"TG_SESSION#{chat_id}", "SK": "STATE"}
        )
        if "Item" in response:
            item = _deserialize_decimals(response["Item"])
            if item.get("ttl", 0) > int(time.time()):
                return item.get("session_data")
        return None

    def delete_telegram_session(self, chat_id: str):
        self.table.delete_item(
            Key={"PK": f"TG_SESSION#{chat_id}", "SK": "STATE"}
        )

    # =================================================================
    # 4. ATOMIC APPROVAL STATE MACHINE (ANTI-DUPLIKASI - P0 #8 & P1 #14)
    # =================================================================
    def save_approval_state(self, state: TelegramApprovalState):
        item = state.model_dump()
        item["PK"] = f"REQ#{state.request_id}"
        item["SK"] = "STATE"
        self.table.put_item(Item=_serialize_decimals(item))

    def get_approval_state(self, request_id: str):
        response = self.table.get_item(
            Key={"PK": f"REQ#{request_id}", "SK": "STATE"}
        )
        if "Item" in response:
            data = _deserialize_decimals(response["Item"])
            return TelegramApprovalState(**data)
        return None

    def transition_approval_state(
        self,
        request_id: str,
        expected_current_statuses: list[str],
        new_status: str,
        final_qty: int = None,
        sap_pr_id: str = None,
        rejection_reason: str = None,
    ) -> bool:
        """
        Melakukan update state secara ATOMIC menggunakan Conditional Write DynamoDB.
        Mengembalikan True jika transisi berhasil, atau False jika sudah diproses oleh request lain.
        """
        # Validasi aturan state machine
        for exp_st in expected_current_statuses:
            allowed_targets = VALID_STATE_TRANSITIONS.get(exp_st, set())
            if new_status not in allowed_targets and new_status != exp_st:
                logger.warning("Transisi state ilegal ditolak: %s -> %s", exp_st, new_status)
                return False

        update_expr = "SET #s = :new_status, updated_at = :now"
        expr_attr_names = {"#s": "status"}
        expr_attr_values = {
            ":new_status": new_status,
            ":now": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Susun ConditionExpression: status saat ini wajib berada di expected_current_statuses
        status_conditions = []
        for idx, st in enumerate(expected_current_statuses):
            key_placeholder = f":exp_{idx}"
            status_conditions.append(f"#s = {key_placeholder}")
            expr_attr_values[key_placeholder] = st

        condition_expr = "attribute_exists(PK) AND (" + " OR ".join(status_conditions) + ")"

        if final_qty is not None:
            update_expr += ", final_qty = :fq"
            expr_attr_values[":fq"] = final_qty
        if sap_pr_id is not None:
            update_expr += ", sap_pr_id = :pr"
            expr_attr_values[":pr"] = sap_pr_id
        if rejection_reason is not None:
            update_expr += ", rejection_reason = :rr"
            expr_attr_values[":rr"] = rejection_reason

        try:
            self.table.update_item(
                Key={"PK": f"REQ#{request_id}", "SK": "STATE"},
                UpdateExpression=update_expr,
                ConditionExpression=condition_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=_serialize_decimals(expr_attr_values),
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "Duplikasi callback / race condition dicegah pada request %s (target: %s)",
                    request_id,
                    new_status,
                )
                return False
            raise

    # Pertahankan alias kompatibilitas
    def update_approval_state(
        self, request_id: str, new_status: str, final_qty: int = None, sap_pr_id: str = None, rejection_reason: str = None
    ):
        return self.transition_approval_state(
            request_id=request_id,
            expected_current_statuses=["PENDING_APPROVAL", "EDIT_REQUESTED", "SAP_SUBMITTING", "APPROVED"],
            new_status=new_status,
            final_qty=final_qty,
            sap_pr_id=sap_pr_id,
            rejection_reason=rejection_reason,
        )

    # =================================================================
    # 5. DISTRIBUTED STORE EVALUATION LOCK (ANTI EVALUASI GANDA - P1 #11)
    # =================================================================
    def acquire_store_eval_lock(self, store_id: str, lock_ttl_seconds: int = 90) -> bool:
        """Mencegah satu toko dievaluasi bersamaan oleh dua proses berbeda."""
        now = int(time.time())
        try:
            self.table.put_item(
                Item={
                    "PK": f"LOCK#STORE#{store_id}",
                    "SK": "EVAL",
                    "locked_at": now,
                    "ttl": now + lock_ttl_seconds,
                },
                ConditionExpression="attribute_not_exists(PK) OR #ttl < :now",
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues={":now": now},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def release_store_eval_lock(self, store_id: str):
        try:
            self.table.delete_item(
                Key={"PK": f"LOCK#STORE#{store_id}", "SK": "EVAL"}
            )
        except Exception:
            pass

    # =================================================================
    # 6. AUDIT LOG
    # =================================================================
    def save_audit_log(self, store_id: str, timestamp_str: str, sku_id: str, audit_data: dict):
        item = {
            "PK": f"AUDIT#{store_id}",
            "SK": f"TS#{timestamp_str}#SKU#{sku_id}",
            "store_id": store_id,
            "sku_id": sku_id,
            "timestamp": timestamp_str,
            **audit_data,
        }
        self.table.put_item(Item=_serialize_decimals(item))

    def get_audit_logs(self, store_id: str = None) -> list[dict]:
        if store_id:
            response = self.table.query(
                KeyConditionExpression=Key("PK").eq(f"AUDIT#{store_id}"),
                ScanIndexForward=False,
                Limit=50,
            )
        else:
            response = self.table.scan(
                FilterExpression=Attr("PK").begins_with("AUDIT#")
            )
        items = _deserialize_decimals(response.get("Items", []))
        return sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)