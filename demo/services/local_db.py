"""SQLite Database Service for AutoReplenish.ai Local Demo.

Replaces DynamoDB with a lightweight SQLite database (PRD Section 13).
Handles stores, skus, inventory, recommendations, feedback_logs, and audit_logs.
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Standardize path resolution: demo/db/demo.db
DEMO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = DEMO_DIR / "db" / "demo.db"


def get_db_path(db_path: Optional[str] = None) -> str:
    """Return standardized absolute path to SQLite database."""
    if db_path:
        p = Path(db_path)
        return str(p if p.is_absolute() else (DEMO_DIR / p).resolve())
    env_path = os.getenv("SQLITE_DB_PATH")
    if env_path:
        p = Path(env_path)
        return str(p if p.is_absolute() else (DEMO_DIR / p).resolve())
    return str(DEFAULT_DB_PATH.resolve())


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and return a SQLite connection with row_factory set to sqlite3.Row."""
    resolved_path = get_db_path(db_path)
    os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
    conn = sqlite3.connect(resolved_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> str:
    """Initialize SQLite database tables matching PRD data models."""
    resolved_path = get_db_path(db_path)
    os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

    with get_db_connection(resolved_path) as conn:
        cursor = conn.cursor()

        # 1. Stores Table (PRD 13.3 StoreMetadata)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            area_type TEXT NOT NULL,
            zone TEXT NOT NULL,
            sap_plant TEXT NOT NULL,
            storage_location TEXT DEFAULT 'WH-01',
            telegram_chat_id TEXT,
            active INTEGER DEFAULT 1
        );
        """)

        # 2. SKUs Table (PRD 13.4 SKUProfile)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS skus (
            sku_id TEXT PRIMARY KEY,
            sku_name TEXT NOT NULL,
            category TEXT NOT NULL,
            weather_sensitive INTEGER DEFAULT 0,
            moq INTEGER NOT NULL DEFAULT 1,
            packaging_multiple INTEGER NOT NULL DEFAULT 1,
            base_unit TEXT DEFAULT 'PCS',
            default_lead_time_days INTEGER DEFAULT 1,
            vendor_id TEXT
        );
        """)

        # 3. Inventory Table (PRD 13.5 Store Inventory Levels)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            store_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            physical_stock INTEGER NOT NULL DEFAULT 0,
            threshold INTEGER NOT NULL DEFAULT 0,
            average_daily_burn_rate INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (store_id, sku_id),
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (sku_id) REFERENCES skus(sku_id)
        );
        """)

        # 4. Recommendations Table (PRD 13.6 TelegramState + Audit Fields)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            request_id TEXT PRIMARY KEY,
            run_id TEXT,
            store_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            recommended_qty INTEGER NOT NULL,
            normal_qty INTEGER NOT NULL,
            adjusted_qty_before_moq INTEGER,
            moq_applied INTEGER DEFAULT 0,
            packaging_multiple_applied INTEGER DEFAULT 0,
            final_qty INTEGER NOT NULL,
            confidence_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            reasoning_narrative TEXT NOT NULL,
            key_factors TEXT,
            warnings TEXT,
            status TEXT NOT NULL,
            telegram_message_id TEXT,
            prompt_version TEXT,
            ai_output TEXT,
            input_context TEXT,
            sap_pr_id TEXT,
            sap_pr_status TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (sku_id) REFERENCES skus(sku_id)
        );
        """)

        # 5. Feedback Logs Table (PRD 13.8 FeedbackLog)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            store_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            original_qty INTEGER,
            final_qty INTEGER,
            created_at TEXT NOT NULL
        );
        """)

        # 6. Audit Logs Table (PRD 13.7 & Section 28)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT,
            created_at TEXT NOT NULL
        );
        """)

        conn.commit()

    return resolved_path


def get_all_stores(active_only: bool = True, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all store metadata records."""
    query = "SELECT * FROM stores"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY store_id ASC"

    with get_db_connection(db_path) as conn:
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]


def get_store_by_id(store_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve single store metadata by store_id."""
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,)).fetchone()
        return dict(row) if row else None


def get_sku_by_id(sku_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve SKU profile by sku_id."""
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM skus WHERE sku_id = ?", (sku_id,)).fetchone()
        return dict(row) if row else None


def get_inventory(store_id: str, sku_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve inventory record for specific store and SKU."""
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM inventory WHERE store_id = ? AND sku_id = ?",
            (store_id, sku_id)
        ).fetchone()
        return dict(row) if row else None


def get_priority_skus(store_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve priority SKUs for a store where physical_stock < threshold (PRD 11.2).
    Includes SKU metadata and inventory levels in a joined result.
    """
    query = """
    SELECT 
        s.sku_id,
        s.sku_name,
        s.category,
        s.weather_sensitive,
        s.moq,
        s.packaging_multiple,
        s.base_unit,
        s.default_lead_time_days,
        s.vendor_id,
        i.store_id,
        i.physical_stock,
        i.threshold,
        i.average_daily_burn_rate
    FROM inventory i
    JOIN skus s ON i.sku_id = s.sku_id
    WHERE i.store_id = ? AND i.physical_stock < i.threshold
    ORDER BY (i.threshold - i.physical_stock) DESC
    """
    with get_db_connection(db_path) as conn:
        rows = conn.execute(query, (store_id,)).fetchall()
        return [dict(row) for row in rows]


def save_recommendation(rec: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Insert new recommendation record into recommendations table."""
    now_iso = datetime.now(timezone.utc).isoformat()
    
    key_factors_json = json.dumps(rec.get("key_factors", [])) if isinstance(rec.get("key_factors"), list) else rec.get("key_factors", "[]")
    warnings_json = json.dumps(rec.get("warnings", [])) if isinstance(rec.get("warnings"), list) else rec.get("warnings", "[]")
    ai_output_json = json.dumps(rec.get("ai_output", {})) if isinstance(rec.get("ai_output"), dict) else rec.get("ai_output", "{}")
    input_context_json = json.dumps(rec.get("input_context", {})) if isinstance(rec.get("input_context"), dict) else rec.get("input_context", "{}")

    with get_db_connection(db_path) as conn:
        conn.execute("""
        INSERT INTO recommendations (
            request_id, run_id, store_id, sku_id,
            recommended_qty, normal_qty, adjusted_qty_before_moq,
            moq_applied, packaging_multiple_applied, final_qty,
            confidence_score, risk_level, reasoning_narrative,
            key_factors, warnings, status, telegram_message_id,
            prompt_version, ai_output, input_context,
            sap_pr_id, sap_pr_status, expires_at, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        """, (
            rec["request_id"],
            rec.get("run_id"),
            rec["store_id"],
            rec["sku_id"],
            rec["recommended_qty"],
            rec["normal_qty"],
            rec.get("adjusted_qty_before_moq", rec["recommended_qty"]),
            1 if rec.get("moq_applied") else 0,
            1 if rec.get("packaging_multiple_applied") else 0,
            rec.get("final_qty", rec["recommended_qty"]),
            rec["confidence_score"],
            rec["risk_level"],
            rec["reasoning_narrative"],
            key_factors_json,
            warnings_json,
            rec.get("status", "PENDING_APPROVAL"),
            rec.get("telegram_message_id"),
            rec.get("prompt_version", "v1.0"),
            ai_output_json,
            input_context_json,
            rec.get("sap_pr_id"),
            rec.get("sap_pr_status"),
            rec.get("expires_at"),
            rec.get("created_at", now_iso),
            rec.get("updated_at", now_iso)
        ))
        conn.commit()


def get_recommendation_by_id(request_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve recommendation by request_id and deserialize JSON fields."""
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM recommendations WHERE request_id = ?", (request_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        for json_col in ["key_factors", "warnings", "ai_output", "input_context"]:
            if data.get(json_col) and isinstance(data[json_col], str):
                try:
                    data[json_col] = json.loads(data[json_col])
                except Exception:
                    pass
        return data


def update_recommendation_status(
    request_id: str,
    status: str,
    db_path: Optional[str] = None,
    **kwargs
) -> None:
    """Update status and optional metadata columns for a recommendation."""
    now_iso = datetime.now(timezone.utc).isoformat()
    fields = ["status = ?", "updated_at = ?"]
    params = [status, now_iso]

    for key, value in kwargs.items():
        if key in ["telegram_message_id", "final_qty", "sap_pr_id", "sap_pr_status"]:
            fields.append(f"{key} = ?")
            params.append(value)
        elif key in ["ai_output", "input_context", "key_factors", "warnings"]:
            fields.append(f"{key} = ?")
            params.append(json.dumps(value) if not isinstance(value, str) else value)

    params.append(request_id)
    query = f"UPDATE recommendations SET {', '.join(fields)} WHERE request_id = ?"

    with get_db_connection(db_path) as conn:
        conn.execute(query, tuple(params))
        conn.commit()


def save_feedback(feedback: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Save user interaction / action feedback log."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO feedback_logs (
            request_id, store_id, sku_id, action, reason, original_qty, final_qty, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback["request_id"],
            feedback["store_id"],
            feedback["sku_id"],
            feedback["action"],
            feedback.get("reason"),
            feedback.get("original_qty"),
            feedback.get("final_qty"),
            feedback.get("created_at", now_iso)
        ))
        conn.commit()
        return cursor.lastrowid


def save_audit_log(audit: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Save audit trail log with full JSON payload."""
    now_iso = datetime.now(timezone.utc).isoformat()
    payload_str = json.dumps(audit.get("payload", {})) if not isinstance(audit.get("payload"), str) else audit.get("payload")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO audit_logs (request_id, event_type, payload, created_at)
        VALUES (?, ?, ?, ?)
        """, (
            audit["request_id"],
            audit["event_type"],
            payload_str,
            audit.get("created_at", now_iso)
        ))
        conn.commit()
        return cursor.lastrowid


def get_all_recommendations(
    store_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve all recommendations with joined store, SKU, and feedback details."""
    query = """
    SELECT 
        r.*,
        s.store_name,
        s.area_type,
        s.zone,
        k.sku_name,
        k.category,
        k.base_unit,
        k.moq,
        k.packaging_multiple,
        k.weather_sensitive,
        k.default_lead_time_days AS lead_time_days,
        inv.physical_stock,
        inv.threshold,
        inv.average_daily_burn_rate,
        fb.action AS human_action_logged,
        fb.reason AS rejection_reason,
        fb.final_qty AS human_final_qty_logged,
        fb.created_at AS feedback_time
    FROM recommendations r
    LEFT JOIN stores s ON r.store_id = s.store_id
    LEFT JOIN skus k ON r.sku_id = k.sku_id
    LEFT JOIN inventory inv ON (r.store_id = inv.store_id AND r.sku_id = inv.sku_id)
    LEFT JOIN (
        SELECT request_id, action, reason, final_qty, created_at,
               ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY id DESC) as rn
        FROM feedback_logs
    ) fb ON r.request_id = fb.request_id AND fb.rn = 1
    WHERE 1=1
    """
    params = []
    if store_id:
        query += " AND r.store_id = ?"
        params.append(store_id)
    if date_from:
        query += " AND r.created_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND r.created_at <= ?"
        params.append(date_to)

    query += " ORDER BY r.created_at DESC"

    with get_db_connection(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            
            # Deserialize JSON columns
            for json_col in ["key_factors", "warnings", "ai_output", "input_context"]:
                if data.get(json_col) and isinstance(data[json_col], str):
                    try:
                        data[json_col] = json.loads(data[json_col])
                    except Exception:
                        pass
            
            # Map human action from status or feedback
            status = data.get("status", "PENDING_APPROVAL")
            human_action = data.get("human_action_logged")
            if not human_action:
                if status in ["APPROVED", "PR_CREATED"]:
                    human_action = "APPROVED"
                elif status == "REJECTED":
                    human_action = "REJECTED"
                elif status == "EDITED":
                    human_action = "EDITED"
                else:
                    human_action = "PENDING"
            
            data["human_action"] = human_action
            data["human_final_qty"] = data.get("human_final_qty_logged") or data.get("final_qty")
            
            # Alias quantity fields for UI compatibility
            data["ai_recommended_qty"] = data.get("recommended_qty")
            data["final_recommended_qty"] = data.get("final_qty", data.get("recommended_qty"))
            
            # Weather & Calendar helpers from input_context if available
            ctx = data.get("input_context", {})
            if isinstance(ctx, dict):
                weather_info = ctx.get("weather", {})
                cal_info = ctx.get("calendar", {})
                data["weather_condition"] = weather_info.get("condition", "Cerah")
                data["calendar_day"] = cal_info.get("day_type", "Weekday")
            else:
                data["weather_condition"] = "Normal"
                data["calendar_day"] = "Weekday"

            data["completed_at"] = data.get("updated_at")
            data["approved_at"] = data.get("updated_at") if human_action == "APPROVED" else None

            result.append(data)
        return result


def get_all_feedback(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all feedback logs."""
    with get_db_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM feedback_logs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def get_inventory_health_for_store(store_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve all inventory records for a store with health classification:
    - stockout_risk: physical_stock < threshold
    - overstock_risk: physical_stock > (threshold * 2.5) and threshold > 0
    - healthy: otherwise
    """
    query = """
    SELECT 
        i.store_id,
        i.sku_id,
        i.physical_stock,
        i.threshold,
        i.average_daily_burn_rate,
        s.sku_name,
        s.category,
        s.weather_sensitive,
        s.moq,
        s.packaging_multiple,
        s.default_lead_time_days AS lead_time_days
    FROM inventory i
    JOIN skus s ON i.sku_id = s.sku_id
    WHERE i.store_id = ?
    ORDER BY i.sku_id ASC
    """
    with get_db_connection(db_path) as conn:
        rows = conn.execute(query, (store_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            stock = item["physical_stock"]
            threshold = item["threshold"]
            burn_rate = max(0.1, float(item["average_daily_burn_rate"]))
            
            # Calculate Days of Supply
            item["days_of_supply"] = round(stock / burn_rate, 1)
            item["weather_sensitive"] = bool(item.get("weather_sensitive", 0))

            if stock < threshold:
                item["status"] = "STOCKOUT_RISK"
                item["health_status"] = "stockout_risk"
            elif threshold > 0 and stock > (threshold * 2.5):
                item["status"] = "OVERSTOCK_RISK"
                item["health_status"] = "overstock_risk"
            else:
                item["status"] = "HEALTHY"
                item["health_status"] = "healthy"

            result.append(item)
        return result
