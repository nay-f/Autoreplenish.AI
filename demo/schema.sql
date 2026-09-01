CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    store_name TEXT,
    area_type TEXT,
    zone TEXT,
    sap_plant TEXT,
    storage_location TEXT,
    telegram_chat_id TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS skus (
    sku_id TEXT PRIMARY KEY,
    sku_name TEXT,
    category TEXT,
    weather_sensitive INTEGER,
    moq INTEGER,
    packaging_multiple INTEGER,
    base_unit TEXT,
    default_lead_time_days INTEGER,
    vendor_id TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    store_id TEXT,
    sku_id TEXT,
    physical_stock INTEGER,
    threshold INTEGER,
    average_daily_burn_rate INTEGER,
    PRIMARY KEY (store_id, sku_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    request_id TEXT PRIMARY KEY,
    run_id TEXT,
    store_id TEXT,
    sku_id TEXT,
    recommended_qty INTEGER,
    normal_qty INTEGER,
    final_qty INTEGER,
    confidence_score REAL,
    risk_level TEXT,
    reasoning_narrative TEXT,
    status TEXT,
    telegram_message_id TEXT,
    prompt_version TEXT,
    ai_output TEXT,
    input_context TEXT,
    sap_pr_id TEXT,
    sap_pr_status TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS feedback_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    store_id TEXT,
    sku_id TEXT,
    action TEXT,
    reason TEXT,
    original_qty INTEGER,
    final_qty INTEGER,
    created_at TEXT
);