"""AWS Lambda entry points for EventBridge, Telegram webhook, and SQS SAP worker."""

import base64
import hmac
import json
import logging

from backend.src import config
from backend.src.services.dynamodb_service import DynamoDBService
from backend.src.services.sap_worker_service import SAPWorkerService

logger = logging.getLogger("autoreplenish.lambda")
MAX_WEBHOOK_BODY_BYTES = 256 * 1024


def _header_value(headers: dict, name: str) -> str:
    for key, value in (headers or {}).items():
        if str(key).lower() == name.lower():
            return str(value or "")
    return ""


def _webhook_is_authorized(headers: dict) -> bool:
    expected = config.TELEGRAM_WEBHOOK_SECRET
    supplied = _header_value(headers, "x-telegram-bot-api-secret-token")
    if not expected:
        return config.ENVIRONMENT == "development"
    return hmac.compare_digest(supplied, expected)


def dashboard_api_handler(event, context):
    """API Gateway adapter for the existing FastAPI dashboard routes."""
    try:
        from mangum import Mangum
        from backend.main import app
        return Mangum(app)(event, context)
    except ImportError as exc:
        logger.error("Mangum belum dipasang untuk dashboard API: %s", exc)
        return {"statusCode": 503, "body": json.dumps({"error": "dashboard adapter unavailable"})}


def telegram_webhook_handler(event, context):
    headers = event.get("headers") or {}
    if not _webhook_is_authorized(headers):
        status = 503 if not config.TELEGRAM_WEBHOOK_SECRET and config.ENVIRONMENT != "development" else 401
        return {"statusCode": status, "body": json.dumps({"error": "invalid webhook"})}
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return {"statusCode": 400, "body": json.dumps({"error": "invalid body encoding"})}
    if len(body.encode("utf-8")) > MAX_WEBHOOK_BODY_BYTES:
        return {"statusCode": 413, "body": json.dumps({"error": "body too large"})}
    try:
        update = json.loads(body)
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON"})}
    if not isinstance(update, dict):
        return {"statusCode": 400, "body": json.dumps({"error": "invalid Telegram update"})}
    from backend.main import handle_telegram_update
    handle_telegram_update(update, allow_long_running=False)
    return {"statusCode": 200, "body": json.dumps({"ok": True})}


def orchestrator_handler(event, context):
    event_environment = str((event or {}).get("environment", config.ENVIRONMENT)).lower()
    if event_environment != config.ENVIRONMENT:
        raise ValueError("EventBridge event environment mismatch")
    from backend.src.services.orchestrator_service import OrchestratorService
    orchestrator = OrchestratorService()
    store_id = (event or {}).get("store_id")
    if store_id:
        return orchestrator.evaluate_store(store_id, force_all=False)
    db = DynamoDBService()
    results = []
    for store in db.list_stores():
        if store.active:
            results.append(orchestrator.evaluate_store(store.store_id, force_all=False))
    return {"evaluated_stores": len(results), "results": results}


def _resolve_store_and_sku(db, store_id, sku_id):
    store = db.get_store(store_id)
    sku = next((item for item in db.get_skus_for_store(store_id) if item.sku_id == sku_id), None)
    if not store or not sku:
        raise ValueError(f"Store/SKU tidak ditemukan: {store_id}/{sku_id}")
    return store, sku


def sap_worker_handler(event, context):
    db = DynamoDBService()
    worker = SAPWorkerService(db=db)
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            message = json.loads(record.get("body", "{}"))
            worker.process(
                message,
                lambda store_id, sku_id, _name: _resolve_store_and_sku(db, store_id, sku_id),
            )
        except Exception:
            logger.exception("SAP worker gagal memproses message %s", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
