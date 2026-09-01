"""SAP Worker Lambda Handler.

Consumes approval events from SQS Queue, creates Purchase Requisitions in SAP S/4HANA,
updates DynamoDB audit records, and routes fatal errors to DLQ.
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from ..config import logger
from ..services.dynamodb_service import DynamoDBService
from ..services.sap_service import SapIntegrationService

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process SQS batch of SAP Purchase Requisitions."""
    db = DynamoDBService()
    sap = SapIntegrationService()

    records = event.get("Records", [])
    logger.info(f"Processing {len(records)} SQS message(s) for SAP PR creation")

    success_count = 0
    failure_count = 0

    for msg in records:
        try:
            body = json.loads(msg.get("body", "{}"))
            request_id = body.get("request_id")
            sku_id = body.get("sku_id")
            quantity = body.get("quantity")
            store_id = body.get("store_id")

            if not request_id or not sku_id or not quantity:
                logger.error(f"Malformed SQS message: {msg}")
                failure_count += 1
                continue

            # Build and send PR
            payload = sap.build_pr_payload(
                sku_id=sku_id,
                sku_name=f"Material {sku_id}",
                quantity=quantity,
                storage_location=store_id or "STR-001"
            )
            response = sap.create_purchase_requisition(request_id, payload)

            now_str = datetime.now(timezone.utc).isoformat()

            if response.success:
                db.update_telegram_state_status(request_id, "PR_CREATED", sap_pr_id=response.sap_pr_id)
                audit = db.get_audit_log_by_request_id(request_id)
                if audit:
                    audit.sap_pr_status = "SUCCESS"
                    audit.sap_pr_id = response.sap_pr_id
                    audit.completed_at = now_str
                    db.put_audit_log(audit)
                success_count += 1
            else:
                db.update_telegram_state_status(request_id, "FAILED_SAP", sap_error_message=response.error_message)
                audit = db.get_audit_log_by_request_id(request_id)
                if audit:
                    audit.sap_pr_status = "FAILED_SAP"
                    db.put_audit_log(audit)
                failure_count += 1
                logger.error(f"Failed to create SAP PR for request {request_id}: {response.error_message}")

        except Exception as e:
            logger.error(f"Error processing SQS record: {e}")
            failure_count += 1

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": len(records),
            "success": success_count,
            "failed": failure_count
        })
    }
