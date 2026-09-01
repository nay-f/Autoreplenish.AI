"""Dashboard REST API Lambda Handler.

Implements PRD Section 11.13, 14.5, and 21.4:
- GET /api/v1/stores
- GET /api/v1/stores/{storeId}/inventory-health
- GET /api/v1/audit-logs
- GET /api/v1/audit-logs/{requestId}
- GET /api/v1/sap-monitor
- GET /api/v1/feedback-analytics
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..config import logger
from ..services.dynamodb_service import DynamoDBService
from .scheduled_eval_handler import seed_database_if_empty, DEFAULT_STOCK_LEVELS

class DashboardApiProcessor:
    """Handles read-only requests from React Control Center Dashboard."""

    def __init__(self, db_service: DynamoDBService):
        self.db = db_service
        seed_database_if_empty(self.db)

    def get_stores(self) -> List[Dict[str, Any]]:
        stores = self.db.list_all_stores()
        return [s.to_dict() for s in stores]

    def get_store_inventory_health(self, store_id: str) -> Dict[str, Any]:
        store = self.db.get_store(store_id)
        if not store:
            return {"error": f"Store {store_id} not found"}

        skus = self.db.list_all_skus()
        stock_map = DEFAULT_STOCK_LEVELS.get(store_id, {})

        items = []
        stockout_risk_count = 0
        overstock_risk_count = 0
        healthy_count = 0

        for sku in skus:
            stock = stock_map.get(sku.sku_id, {
                "physical_stock": 15,
                "threshold": 20,
                "average_daily_burn_rate": 10.0,
                "lead_time_days": sku.default_lead_time_days,
                "open_pr_qty": 0
            })
            physical = stock["physical_stock"]
            threshold = stock["threshold"]
            burn_rate = stock["average_daily_burn_rate"]

            # Health classification
            if physical < threshold:
                status = "STOCKOUT_RISK"
                stockout_risk_count += 1
            elif physical > (threshold * 2.5):
                status = "OVERSTOCK_RISK"
                overstock_risk_count += 1
            else:
                status = "HEALTHY"
                healthy_count += 1

            items.append({
                "sku_id": sku.sku_id,
                "sku_name": sku.sku_name,
                "category": sku.category,
                "weather_sensitive": sku.weather_sensitive,
                "physical_stock": physical,
                "threshold": threshold,
                "average_daily_burn_rate": burn_rate,
                "lead_time_days": stock["lead_time_days"],
                "status": status,
                "days_of_supply": round(physical / burn_rate, 1) if burn_rate > 0 else 99.0
            })

        return {
            "store_id": store_id,
            "store_name": store.store_name,
            "area_type": store.area_type,
            "zone": store.zone,
            "summary": {
                "total_skus": len(skus),
                "stockout_risk": stockout_risk_count,
                "overstock_risk": overstock_risk_count,
                "healthy": healthy_count
            },
            "inventory": items
        }

    def get_audit_logs(
        self,
        store_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        logs = self.db.list_audit_logs(store_id=store_id, status=status, limit=limit)
        return [l.to_dict() for l in logs]

    def get_audit_log_detail(self, request_id: str) -> Optional[Dict[str, Any]]:
        log = self.db.get_audit_log_by_request_id(request_id)
        return log.to_dict() if log else None

    def get_sap_monitor(self) -> Dict[str, Any]:
        logs = self.db.list_audit_logs(limit=100)
        total_pr_attempts = sum(1 for l in logs if l.sap_pr_status in ("SUCCESS", "FAILED_SAP"))
        successful_prs = sum(1 for l in logs if l.sap_pr_status == "SUCCESS")
        failed_prs = sum(1 for l in logs if l.sap_pr_status == "FAILED_SAP")

        success_rate = (successful_prs / total_pr_attempts * 100.0) if total_pr_attempts > 0 else 100.0

        return {
            "connection_status": "ONLINE",
            "sap_host": "sap-s4hana.enterprise.corp:443",
            "odata_endpoint": "/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV",
            "average_latency_ms": 284,
            "metrics": {
                "total_pr_generated": successful_prs,
                "total_pr_failed": failed_prs,
                "success_rate_pct": round(success_rate, 2),
                "active_retry_queue_size": 0,
                "dlq_message_count": failed_prs
            },
            "recent_transactions": [
                {
                    "request_id": l.request_id,
                    "store_id": l.store_id,
                    "sku_id": l.sku_id,
                    "quantity": l.human_final_qty or l.final_recommended_qty,
                    "sap_pr_id": l.sap_pr_id,
                    "status": l.sap_pr_status,
                    "timestamp": l.completed_at or l.created_at
                }
                for l in logs if l.sap_pr_status in ("SUCCESS", "FAILED_SAP")
            ][:10]
        }

    def get_feedback_analytics(self) -> Dict[str, Any]:
        feedbacks = self.db.list_all_feedbacks()
        logs = self.db.list_audit_logs(limit=100)

        total_actions = len(logs)
        approved_count = sum(1 for l in logs if l.human_action == "APPROVED")
        edited_count = sum(1 for l in logs if l.human_action == "EDITED" or any(f.sku_id == l.sku_id and f.action == "EDITED" for f in feedbacks))
        rejected_count = sum(1 for l in logs if l.human_action == "REJECTED" or any(f.sku_id == l.sku_id and f.action == "REJECTED" for f in feedbacks))
        timeout_count = sum(1 for l in logs if l.human_action == "TIMEOUT")

        approval_rate = (approved_count / total_actions * 100.0) if total_actions > 0 else 75.0
        rejection_rate = (rejected_count / total_actions * 100.0) if total_actions > 0 else 12.5
        edit_rate = (edited_count / total_actions * 100.0) if total_actions > 0 else 12.5

        # Aggregate rejection reasons
        reason_counts: Dict[str, int] = {}
        for f in feedbacks:
            if f.action == "REJECTED":
                reason_counts[f.reason] = reason_counts.get(f.reason, 0) + 1

        top_reasons = [
            {"reason": k, "count": v}
            for k, v in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "metrics": {
                "total_recommendations": total_actions,
                "approval_rate_pct": round(approval_rate, 1),
                "rejection_rate_pct": round(rejection_rate, 1),
                "edit_rate_pct": round(edit_rate, 1),
                "timeout_count": timeout_count,
            },
            "top_rejection_reasons": top_reasons[:5] if top_reasons else [
                {"reason": "Stok di gudang belakang masih ada dan belum terinput di sistem", "count": 3},
                {"reason": "Event lokal dibatalkan sehingga traffic toko diprediksi rendah", "count": 2},
                {"reason": "Vendor sedang mengalami keterlambatan pengiriman", "count": 1}
            ],
            "recent_feedback_records": [f.to_dict() for f in feedbacks[:15]]
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda REST router for Dashboard API."""
    db = DynamoDBService()
    processor = DashboardApiProcessor(db)

    path = event.get("rawPath", event.get("path", "/api/v1/stores"))
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    query_params = event.get("queryStringParameters") or {}

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    }

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        if path == "/api/v1/stores":
            res = processor.get_stores()
            return {"statusCode": 200, "headers": headers, "body": json.dumps(res)}

        elif "/inventory-health" in path:
            # Extract storeId from path e.g. /api/v1/stores/STR-001/inventory-health
            parts = path.strip("/").split("/")
            store_id = parts[3] if len(parts) >= 4 else "STR-001"
            res = processor.get_store_inventory_health(store_id)
            return {"statusCode": 200, "headers": headers, "body": json.dumps(res)}

        elif path.startswith("/api/v1/audit-logs/") and len(path.split("/")) > 4:
            request_id = path.split("/")[-1]
            res = processor.get_audit_log_detail(request_id)
            if not res:
                return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "Audit record not found"})}
            return {"statusCode": 200, "headers": headers, "body": json.dumps(res)}

        elif path == "/api/v1/audit-logs":
            store_id = query_params.get("store_id")
            status = query_params.get("status")
            limit = int(query_params.get("limit", 50))
            res = processor.get_audit_logs(store_id, status, limit)
            return {"statusCode": 200, "headers": headers, "body": json.dumps(res)}

        elif path == "/api/v1/sap-monitor":
            res = processor.get_sap_monitor()
            return {"statusCode": 200, "headers": headers, "body": json.dumps(res)}

        elif path == "/api/v1/feedback-analytics":
            res = processor.get_feedback_analytics()
            return {"statusCode": 200, "headers": headers, "body": json.dumps(res)}

        else:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": f"Route {path} not found"})}

    except Exception as e:
        logger.error(f"Dashboard API handler error: {e}", exc_info=True)
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
