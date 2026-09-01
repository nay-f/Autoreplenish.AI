#!/usr/bin/env python3
"""Local FastAPI Server for AutoReplenish.ai Dashboard.

Exposes REST API endpoints matching PRD Section 14.5 and the React Dashboard UI components.
Reads real-time state from SQLite database (demo/db/demo.db).
"""

import os
import sys
from collections import Counter
from typing import Optional, List, Dict, Any

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

env_demo = os.path.join(BASE_DIR, ".env")
env_root = os.path.join(os.path.dirname(BASE_DIR), ".env")
if os.path.exists(env_demo):
    load_dotenv(env_demo)
elif os.path.exists(env_root):
    load_dotenv(env_root)
else:
    load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from services.local_db import (
    get_all_stores,
    get_store_by_id,
    get_inventory_health_for_store,
    get_all_recommendations,
    get_recommendation_by_id,
    get_all_feedback,
    get_db_connection,
)
from services.mock_sap import check_sap_connection

app = FastAPI(
    title="AutoReplenish.ai Local Demo API",
    description="Live REST API for Multi-Store Inventory, AI Audit Trail, SAP Monitor, and Feedback Analytics",
    version="1.0.0",
)

# Enable CORS for frontend dashboard (port 3000 / all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def get_health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AutoReplenish.ai Local Demo API",
        "mode": os.getenv("DEMO_MODE", "local"),
        "database": "sqlite",
    }


@app.get("/stores")
def list_stores(active_only: bool = True):
    """Retrieve list of all active retail stores (PRD 13.3)."""
    return get_all_stores(active_only=active_only)


@app.get("/stores/{store_id}/inventory-health")
def get_store_inventory_health(store_id: str):
    """
    Get current stock levels, thresholds, and health classifications for a specific store.
    Format matches InventoryHealth.jsx component expectations.
    """
    store = get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store '{store_id}' not found.")
    
    inventory_items = get_inventory_health_for_store(store_id)
    stockout_count = sum(1 for item in inventory_items if item.get("status") == "STOCKOUT_RISK")
    overstock_count = sum(1 for item in inventory_items if item.get("status") == "OVERSTOCK_RISK")
    healthy_count = sum(1 for item in inventory_items if item.get("status") == "HEALTHY")

    return {
        "store_id": store["store_id"],
        "store_name": store["store_name"],
        "area_type": store["area_type"],
        "zone": store["zone"],
        "summary": {
            "total_skus": len(inventory_items),
            "stockout_risk": stockout_count,
            "overstock_risk": overstock_count,
            "healthy": healthy_count,
        },
        "inventory": inventory_items,
        # Backward compatibility fields
        "store": store,
        "items": inventory_items,
        "total_items": len(inventory_items),
        "stockout_risk_count": stockout_count,
        "overstock_risk_count": overstock_count,
        "healthy_count": healthy_count,
    }


@app.get("/audit-logs")
def list_audit_logs(
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    date_from: Optional[str] = Query(None, description="Filter start date ISO"),
    date_to: Optional[str] = Query(None, description="Filter end date ISO"),
):
    """
    List recommendation history and audit summaries.
    Returns Array directly for seamless consumption in ReasoningTrace.jsx.
    """
    recs = get_all_recommendations(store_id=store_id, date_from=date_from, date_to=date_to)
    return recs


@app.get("/audit-logs/{request_id}")
def get_audit_log_detail(request_id: str):
    """
    Retrieve deep reasoning audit trace for a specific replenishment request (PRD Section 11.12, 28).
    """
    rec = get_recommendation_by_id(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation '{request_id}' not found.")

    store = get_store_by_id(rec["store_id"])
    
    with get_db_connection() as conn:
        fb_row = conn.execute(
            "SELECT * FROM feedback_logs WHERE request_id = ? ORDER BY id DESC LIMIT 1",
            (request_id,)
        ).fetchone()
        feedback = dict(fb_row) if fb_row else None

        audit_rows = conn.execute(
            "SELECT * FROM audit_logs WHERE request_id = ? ORDER BY id ASC",
            (request_id,)
        ).fetchall()
        audit_trail = [dict(r) for r in audit_rows]

    return {
        "request_id": rec["request_id"],
        "run_id": rec.get("run_id"),
        "store": store,
        "sku_id": rec["sku_id"],
        "status": rec["status"],
        "prompt_version": rec.get("prompt_version", "v1.0"),
        "model": os.getenv("MODEL_NAME", "anthropic.claude-3-5-sonnet"),
        "recommended_qty": rec["recommended_qty"],
        "normal_qty": rec["normal_qty"],
        "final_qty": rec.get("final_qty", rec["recommended_qty"]),
        "confidence_score": rec["confidence_score"],
        "risk_level": rec["risk_level"],
        "reasoning_narrative": rec["reasoning_narrative"],
        "key_factors": rec.get("key_factors", []),
        "warnings": rec.get("warnings", []),
        "sap_pr_id": rec.get("sap_pr_id"),
        "sap_pr_status": rec.get("sap_pr_status"),
        "input_context": rec.get("input_context"),
        "ai_output": rec.get("ai_output"),
        "feedback": feedback,
        "audit_trail": audit_trail,
        "created_at": rec["created_at"],
        "updated_at": rec["updated_at"],
    }


@app.get("/sap-monitor")
def get_sap_monitor():
    """
    Get live SAP S/4HANA connection status and Purchase Requisitions created from SQLite.
    Format matches SapMonitor.jsx component expectations.
    """
    conn_status = check_sap_connection()

    with get_db_connection() as conn:
        # Fetch all recommendations that produced a PR
        pr_rows = conn.execute("""
        SELECT request_id, store_id, sku_id, final_qty as quantity, sap_pr_id, updated_at as timestamp,
               CASE WHEN sap_pr_status LIKE '%FAIL%' THEN 'FAILED' ELSE 'SUCCESS' END as status
        FROM recommendations
        WHERE sap_pr_id IS NOT NULL AND sap_pr_id != ''
        ORDER BY updated_at DESC
        """).fetchall()

        recent_txs = [dict(r) for r in pr_rows]
        total_prs = len(recent_txs)
        failed_prs = sum(1 for t in recent_txs if t.get("status") == "FAILED")
        success_rate = 100.0 if total_prs == 0 else round(((total_prs - failed_prs) / total_prs) * 100, 1)

    return {
        "connection_status": "ONLINE",
        "sap_host": "sap-s4hana.enterprise.corp:443",
        "odata_endpoint": "/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV",
        "average_latency_ms": conn_status.get("latency_ms", 42),
        "metrics": {
            "total_pr_generated": total_prs,
            "total_pr_failed": failed_prs,
            "success_rate_pct": success_rate,
            "active_retry_queue_size": 0,
            "dlq_message_count": 0,
        },
        "recent_transactions": recent_txs,
    }


@app.get("/feedback-analytics")
def get_feedback_analytics():
    """
    Retrieve live feedback analytics computed from SQLite recommendations & feedback_logs.
    Format matches FeedbackAnalytics.jsx component expectations.
    """
    with get_db_connection() as conn:
        all_recs = conn.execute("SELECT status FROM recommendations").fetchall()
        total_recs = len(all_recs)

        feedbacks = conn.execute("""
        SELECT 
            fb.id, fb.request_id, fb.store_id, fb.sku_id, fb.action, fb.reason,
            fb.original_qty as original_recommended_qty, fb.final_qty, fb.created_at
        FROM feedback_logs fb
        ORDER BY fb.id DESC
        """).fetchall()

        feedback_list = [dict(f) for f in feedbacks]
        total_actions = len(feedback_list)

        approved_count = sum(1 for f in feedback_list if f.get("action") == "APPROVED")
        edited_count = sum(1 for f in feedback_list if f.get("action") == "EDITED")
        rejected_count = sum(1 for f in feedback_list if f.get("action") == "REJECTED")

        # Rejection reason frequency
        rejection_reasons = [
            f["reason"].strip() for f in feedback_list 
            if f.get("action") == "REJECTED" and f.get("reason") and f["reason"].strip()
        ]
        reason_counts = Counter(rejection_reasons)
        top_rejections = [
            {"reason": reason, "count": count}
            for reason, count in reason_counts.most_common(5)
        ]

        # Calculate rates based on total actions or recommendations
        denom = max(1, total_actions if total_actions > 0 else total_recs)
        approval_rate = round((approved_count / denom) * 100, 1) if denom > 0 else 0.0
        rejection_rate = round((rejected_count / denom) * 100, 1) if denom > 0 else 0.0
        edit_rate = round((edited_count / denom) * 100, 1) if denom > 0 else 0.0

    return {
        "metrics": {
            "total_recommendations": total_recs,
            "total_actions": total_actions,
            "approval_rate_pct": approval_rate,
            "rejection_rate_pct": rejection_rate,
            "edit_rate_pct": edit_rate,
            "timeout_count": 0,
        },
        "top_rejection_reasons": top_rejections,
        "recent_feedback_records": feedback_list[:10],
    }


def main():
    port = int(os.getenv("DASHBOARD_API_PORT", 8000))
    print("=" * 65)
    print(f"🚀 AUTOREPLENISH.AI — DASHBOARD FASTAPI SERVER")
    print(f"🌐 Live API URL: http://localhost:{port}")
    print("📋 Available Endpoints:")
    print("   • GET  /health")
    print("   • GET  /stores")
    print("   • GET  /stores/{store_id}/inventory-health")
    print("   • GET  /audit-logs")
    print("   • GET  /audit-logs/{request_id}")
    print("   • GET  /sap-monitor")
    print("   • GET  /feedback-analytics")
    print("   • GET  /docs (Interactive Swagger UI)")
    print("=" * 65)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
