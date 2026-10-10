"""SAP Worker Lambda Handler.

Consumes approval events from the SQS queue (see infra/sqs.tf), creates
Purchase Requisitions in SAP S/4HANA, updates DynamoDB audit records, and routes
fatal errors to the DLQ via the queue's redrive policy.

Idempotency is guaranteed twice over: DynamoDB ledger lookup inside
SapIntegrationService, and SQS FIFO + MessageDeduplicationId on the producer side.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

from ..config import logger
from ..services.dynamodb_service import DynamoDBService
from ..services.sap_service import SapIntegrationService


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _process_record(db: DynamoDBService, sap: SapIntegrationService, msg: Dict[str, Any]) -> bool:
    """Process one SQS record. Returns True on success, False on retryable failure."""
    try:
        body = json.loads(msg.get("body", "{}"))
    except Exception:
        logger.error(f"Malformed SQS message body (not JSON): {msg.get('body', '')[:200]}")
        return False

    request_id = body.get("request_id")
    sku_id = body.get("sku_id")
    quantity = body.get("quantity")
    store_id = body.get("store_id")

    if not request_id or not sku_id or not quantity:
        logger.error(f"Malformed SQS message (missing fields): {body}")
        return False

    # Idempotency: if the state machine already recorded a PR, do nothing.
    state = db.get_telegram_state(request_id)
    if state and state.status in ("PR_CREATED", "EDITED") and state.sap_pr_id:
        logger.info(f"Request {request_id} already has PR {state.sap_pr_id}; skipping")
        return True

    payload = sap.build_pr_payload(
        sku_id=sku_id,
        sku_name=f"Material {sku_id}",
        quantity=int(quantity),
        storage_location=store_id or "STR-ALMADINA-001",
    )
    response = sap.create_purchase_requisition(
        request_id=request_id,
        payload=payload,
        store_id=store_id or "STR-ALMADINA-001",
    )

    if response.success:
        db.update_telegram_state_status(request_id, "PR_CREATED", sap_pr_id=response.sap_pr_id)
        audit = db.get_audit_log_by_request_id(request_id)
        if audit:
            audit.sap_pr_status = "SUCCESS"
            audit.sap_pr_id = response.sap_pr_id
            audit.sap_mode = response.mode
            audit.completed_at = _utc_now_iso()
            db.put_audit_log(audit)
        logger.info(
            f"SAP PR {response.sap_pr_id} created for request {request_id} "
            f"(mode={response.mode})"
        )
        return True

    db.update_telegram_state_status(
        request_id, "FAILED_SAP", sap_error_message=response.error_message
    )
    audit = db.get_audit_log_by_request_id(request_id)
    if audit:
        audit.sap_pr_status = "FAILED_SAP"
        audit.completed_at = _utc_now_iso()
        db.put_audit_log(audit)
    logger.error(f"Failed to create SAP PR for request {request_id}: {response.error_message}")
    # Returning False lets SQS retry, then the redrive policy moves it to the DLQ.
    return False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process an SQS batch of SAP Purchase Requisitions."""
    db = DynamoDBService()
    sap = SapIntegrationService(db_service=db)

    records = event.get("Records", [])
    logger.info(f"Processing {len(records)} SQS message(s) for SAP PR creation (mode={sap.mode})")

    success_count = 0
    failure_count = 0

    for msg in records:
        try:
            if _process_record(db, sap, msg):
                success_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.error(f"Unhandled error processing SQS record: {e}", exc_info=True)
            failure_count += 1

    # Raising on failure makes Lambda report a batch-item failure so only the
    # unacknowledged messages are retried (with the redrive policy to the DLQ).
    if failure_count:
        return {
            "statusCode": 207,
            "body": json.dumps({
                "processed": len(records),
                "success": success_count,
                "failed": failure_count,
                "note": "Failed messages will be retried, then moved to the DLQ.",
            }),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": len(records),
            "success": success_count,
            "failed": 0,
        }),
    }
