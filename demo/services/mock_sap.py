"""Mock SAP S/4HANA OData / RFC Service for AutoReplenish.ai Demo.

Simulates Purchase Requisition creation with strict idempotency (PRD Section 11.9, 14.2, 15.6).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# In-memory store for idempotency tracking across calls
_CREATED_PRS: Dict[str, Dict[str, Any]] = {}
_PR_COUNTER: int = 4500012340


def check_sap_connection() -> Dict[str, Any]:
    """Return mock SAP S/4HANA connection status."""
    return {
        "connected": True,
        "system_id": "S4H_DEMO_100",
        "client": "100",
        "latency_ms": 42,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "HEALTHY",
    }


def build_pr_payload(
    store: Dict[str, Any],
    sku: Dict[str, Any],
    recommendation: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Construct SAP S/4HANA standard Purchase Requisition payload (PRD Section 11.9).
    """
    lead_time = int(sku.get("default_lead_time_days", sku.get("lead_time_days", 2)))
    delivery_date = (datetime.now() + timedelta(days=lead_time)).strftime("%Y-%m-%d")
    final_qty = int(recommendation.get("final_qty", recommendation.get("recommended_qty", 1)))

    return {
        "PurchaseRequisitionType": "NB",
        "PurchaseRequisitionItems": [
            {
                "Material": sku.get("sku_id", "SKU-UNKNOWN"),
                "Plant": store.get("sap_plant", "1000"),
                "StoreLocation": store.get("store_id", "STR-001"),
                "RequestedQuantity": final_qty,
                "BaseUnit": sku.get("base_unit", "PCS"),
                "DeliveryDate": delivery_date,
                "ShortText": f"AutoReplenish.ai - {sku.get('sku_name', 'Barang')}",
            }
        ],
    }


def create_purchase_requisition(
    request_id: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create Purchase Requisition in mock SAP S/4HANA.
    
    Enforces idempotency:
    - If request_id has already been processed, returns the existing PR without creating duplicates.
    """
    global _PR_COUNTER, _CREATED_PRS

    now_iso = datetime.now(timezone.utc).isoformat()

    # Idempotency check
    if request_id in _CREATED_PRS:
        existing = _CREATED_PRS[request_id]
        return {
            "status": "SUCCESS",
            "purchase_requisition_id": existing["purchase_requisition_id"],
            "message": "Purchase Requisition telah dibuat sebelumnya (Idempotent response).",
            "idempotent": True,
            "sap_response": existing["sap_response"],
            "timestamp": now_iso,
        }

    # Generate next PR ID
    _PR_COUNTER += 1
    pr_id = f"PR-{_PR_COUNTER}"

    sap_response = {
        "d": {
            "PurchaseRequisition": str(_PR_COUNTER),
            "PurchaseRequisitionType": payload.get("PurchaseRequisitionType", "NB"),
            "CreationDate": now_iso,
            "Items": payload.get("PurchaseRequisitionItems", []),
        }
    }

    record = {
        "request_id": request_id,
        "purchase_requisition_id": pr_id,
        "payload": payload,
        "sap_response": sap_response,
        "created_at": now_iso,
    }
    _CREATED_PRS[request_id] = record

    return {
        "status": "SUCCESS",
        "purchase_requisition_id": pr_id,
        "message": "Purchase Requisition berhasil dibuat.",
        "idempotent": False,
        "sap_response": sap_response,
        "timestamp": now_iso,
    }


def get_all_sap_prs() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all created PRs."""
    return _CREATED_PRS.copy()


def get_sap_stats() -> Dict[str, Any]:
    """Return PR stats for monitoring endpoint."""
    total_created = len(_CREATED_PRS)
    return {
        "total_prs_created": total_created,
        "successful_prs": total_created,
        "failed_prs": 0,
        "success_rate": 100.0 if total_created > 0 else 100.0,
        "last_pr_id": f"PR-{_PR_COUNTER}" if total_created > 0 else None,
    }
