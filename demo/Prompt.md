# 🎯 Prompt untuk Antigravity — Cek & Perbaiki Demo Lokal

Copy-paste seluruh prompt di bawah ini ke Antigravity. Prompt ini dirancang untuk mendiagnosis dan memperbaiki masalah dashboard yang tidak sinkron dengan bot listener, serta memverifikasi seluruh alur demo.

---

```markdown
# TASK: Diagnose, Fix, and Verify Local Demo Data Synchronization for AutoReplenish.ai

You are acting as a Senior Product Architect, Full-Stack Developer, and QA Engineer combined. Read the attached PRD.md and walkthrough.md as the single source of truth.

## CONTEXT

A local demo of AutoReplenish.ai has been built inside the `demo/` folder. This demo runs 100% locally without AWS, without any cloud account, and without any credit card. The architecture is:

```
Telegram Bot (real API, long polling)
        |
        v
Telegram Listener (04_telegram_listener.py)
        |
        v
SQLite Database (demo/db/demo.db)
        ^
        |
Dashboard API (05_dashboard_api.py, FastAPI, port 8000)
        ^
        |
Dashboard React UI (port 3000)
```

The demo consists of these files:
```
demo/
 ├── .env
 ├── requirements.txt
 ├── services/
 │   ├── __init__.py
 │   ├── local_db.py
 │   ├── mock_bedrock.py
 │   ├── mock_sap.py
 │   ├── mock_weather.py
 │   └── telegram_bot.py
 ├── scripts/
 │   ├── 00_check_setup.py
 │   ├── 01_init_db.py
 │   ├── 02_seed_demo.py
 │   ├── 03_run_pipeline.py
 │   ├── 04_telegram_listener.py
 │   └── 05_dashboard_api.py
 └── db/
     └── demo.db
```

Additionally, the original dashboard React app lives in `dashboard/` with `dashboard/src/services/api.js` as the REST API client with mock fallback.

## PROBLEM REPORTED

The dashboard website running on port 3000 displays data that does NOT match the output of the Telegram bot listener. Specifically:

1. When the user clicks Approve/Edit/Reject on Telegram, the Telegram listener processes it correctly and updates the SQLite database.
2. However, the dashboard on port 3000 shows different/stale/mock data that does not reflect the Telegram listener's actions.
3. The data flow is broken somewhere between: Telegram Listener → SQLite → Dashboard API → Dashboard UI.

## YOUR TASK

Perform a complete diagnosis, fix ALL issues found, and verify the entire demo flow end-to-end. Follow these steps precisely:

---

### STEP 1: Audit the Data Flow

Trace the data flow and identify where the break occurs. Check each of these layers:

**Layer A: Telegram Listener → SQLite**
- Read `demo/scripts/04_telegram_listener.py`
- Verify that when APPROVE/EDIT/REJECT callbacks are received, the listener writes to the correct SQLite database file.
- Verify the database path used by the listener matches `demo/db/demo.db`.
- Check if the listener uses `services/local_db.py` correctly.
- Check if there are any hardcoded database paths that point to a different location.

**Layer B: SQLite → Dashboard API**
- Read `demo/scripts/05_dashboard_api.py`
- Verify that the FastAPI server reads from the SAME SQLite database file (`demo/db/demo.db`).
- Check if the database path resolution is consistent (relative vs absolute path issues).
- Verify all endpoints return data from the live database, not from hardcoded/mock data:
  - `GET /stores`
  - `GET /stores/{store_id}/inventory-health`
  - `GET /audit-logs`
  - `GET /audit-logs/{request_id}`
  - `GET /sap-monitor`
  - `GET /feedback-analytics`
  - `GET /health`

**Layer C: Dashboard API → Dashboard React UI**
- Read `dashboard/src/services/api.js`
- Identify the API base URL configuration.
- Check if there is a mock fallback mechanism that activates when the API is unreachable.
- Determine if the dashboard is calling the correct API URL (should be `http://localhost:8000`).
- Check if there are any hardcoded mock data arrays in `api.js` or in the page components.
- Read each dashboard page component:
  - `dashboard/src/pages/InventoryHealth.jsx`
  - `dashboard/src/pages/ReasoningTrace.jsx`
  - `dashboard/src/pages/SapMonitor.jsx`
  - `dashboard/src/pages/FeedbackAnalytics.jsx`
- Check if any page component has its own local mock data that overrides the API response.

**Layer D: CORS and Connectivity**
- Verify that the FastAPI server has CORS enabled for all origins.
- Verify that the dashboard can reach `http://localhost:8000` from port 3000.
- Check for any proxy configuration in `dashboard/vite.config.js` or `dashboard/package.json` that might redirect API calls.

---

### STEP 2: Fix ALL Issues Found

For every issue identified in Step 1, apply the fix directly. Common fixes expected:

1. **If `api.js` has a mock fallback that hides API errors:**
   - Disable the mock fallback or make it explicit (log a warning to console).
   - Ensure the API base URL points to `http://localhost:8000`.
   - If using environment variables, ensure the `.env` file in `dashboard/` is set correctly.

2. **If dashboard pages have hardcoded mock data:**
   - Remove or disable the hardcoded data.
   - Ensure pages fetch from the API service.

3. **If database paths are inconsistent:**
   - Standardize ALL database path resolution to use a single source of truth.
   - Recommended: use `Path(__file__).resolve().parent.parent / "db" / "demo.db"` in all services and scripts.
   - Ensure `.env` `SQLITE_DB_PATH` is read consistently.

4. **If CORS is missing:**
   - Add CORSMiddleware to the FastAPI app in `05_dashboard_api.py`.

5. **If the dashboard API port conflicts with the React dev server port:**
   - Ensure Dashboard API runs on port 8000.
   - Ensure React dashboard runs on port 3000.
   - Ensure they do not conflict.

6. **If `vite.config.js` has a proxy that interferes:**
   - Review and fix the proxy configuration.
   - Ensure `/api` or direct API calls route to `http://localhost:8000`.

7. **If the Dashboard API returns data in a different format than what the React pages expect:**
   - Align the API response format with what the React components consume.
   - Check field names: e.g., `request_id` vs `requestId`, `store_id` vs `storeId`, `sap_pr_id` vs `sapPrId`.
   - Ensure the API response matches the PRD data model (Section 13) and the dashboard PRD requirements (Section 11.13).

---

### STEP 3: Verify Data Synchronization

After applying fixes, verify the complete data flow with a test scenario. Create a verification script `demo/scripts/06_verify_sync.py` that does the following:

1. **Reset the database:**
   - Delete `demo/db/demo.db` if it exists.
   - Run `01_init_db.py` logic to recreate tables.
   - Run `02_seed_demo.py` logic to seed data.

2. **Simulate a pipeline run:**
   - Run the pipeline logic from `03_run_pipeline.py` programmatically (without sending Telegram messages to avoid dependency on Telegram during verification).
   - Save the `request_id` generated.

3. **Simulate an APPROVE action:**
   - Call the approve logic directly (same as what `04_telegram_listener.py` does when it receives `APPROVE:{request_id}`).
   - Verify that:
     - Status changes to `APPROVED` then `PR_CREATED`.
     - A `sap_pr_id` is generated.
     - Feedback log is saved.
     - Audit log is updated.

4. **Simulate an EDIT action:**
   - Run the pipeline again to get a second `request_id`.
   - Simulate EDIT with new quantity.
   - Verify the final_qty is updated.

5. **Simulate a REJECT action:**
   - Run the pipeline again to get a third `request_id`.
   - Simulate REJECT with a reason.
   - Verify status is `REJECTED` and feedback is saved.

6. **Verify Dashboard API returns correct data:**
   - Start the FastAPI app programmatically or use TestClient.
   - Call `GET /audit-logs` and verify all 3 request_ids appear with correct statuses.
   - Call `GET /audit-logs/{request_id}` for each and verify full trace data.
   - Call `GET /sap-monitor` and verify PR counts.
   - Call `GET /feedback-analytics` and verify approval/edit/rejection counts.

7. **Print a verification report:**
   ```
   ============================================================
   🔍 AUTOREPLENISH.AI — Data Synchronization Verification
   ============================================================
   
   Layer A: Telegram Listener → SQLite
   [✅/❌] APPROVE writes to SQLite correctly
   [✅/❌] EDIT writes to SQLite correctly
   [✅/❌] REJECT writes to SQLite correctly
   [✅/❌] Database path is consistent
   
   Layer B: SQLite → Dashboard API
   [✅/❌] /audit-logs returns all records
   [✅/❌] /audit-logs/{id} returns full trace
   [✅/❌] /sap-monitor returns correct PR counts
   [✅/❌] /feedback-analytics returns correct stats
   [✅/❌] Database path is consistent
   
   Layer C: Dashboard API → Dashboard UI
   [✅/❌] api.js points to http://localhost:8000
   [✅/❌] Mock fallback is disabled or explicit
   [✅/❌] Page components fetch from API (not hardcoded)
   [✅/❌] Field names match between API and components
   
   Layer D: CORS and Connectivity
   [✅/❌] CORS is enabled
   [✅/❌] No port conflicts
   [✅/❌] No proxy misconfiguration
   
   ============================================================
   RESULT: [ALL PASSED / X ISSUES FOUND]
   ============================================================
   ```

---

### STEP 4: Fix Dashboard React Components if Needed

If the dashboard React components need changes to properly display the data from the local demo API, apply those changes. Ensure:

1. **InventoryHealth.jsx** shows:
   - All 3 stores from seed data.
   - SKU stock vs threshold.
   - Risk classification (stockout_risk, overstock_risk, healthy).
   - Matches PRD Section 11.13.1.

2. **ReasoningTrace.jsx** shows:
   - All recommendations with request_id.
   - Clicking a recommendation shows full trace: input_context, prompt_version, bedrock_output, confidence_score, reasoning_narrative, key_factors, warnings, human_action, human_final_qty, sap_pr_id.
   - Matches PRD Section 11.13.2 and Section 28.

3. **SapMonitor.jsx** shows:
   - SAP connection status (mock).
   - PR creation success rate.
   - Failed PR count.
   - Matches PRD Section 11.13.3.

4. **FeedbackAnalytics.jsx** shows:
   - Approval rate, rejection rate, edit rate.
   - Top rejection reasons.
   - Matches PRD Section 11.13.4.

---

### STEP 5: Update README_DEMO.md

Update `demo/README_DEMO.md` to include:
- The correct port configuration (API on 8000, Dashboard on 3000).
- The data flow diagram.
- Troubleshooting section for "dashboard data not matching bot listener".
- The verification script usage: `python scripts/06_verify_sync.py`.

---

## CONSTRAINTS

1. Do NOT modify any files outside `demo/` and `dashboard/` folders.
2. Do NOT introduce new external dependencies beyond what's in `demo/requirements.txt` and `dashboard/package.json`.
3. Do NOT use AWS services. Everything must remain local.
4. Do NOT hardcode any secrets. All secrets must come from `.env`.
5. All user-facing text must remain in Bahasa Indonesia.
6. All fixes must maintain compatibility with the PRD data model (Section 13) and audit requirements (Section 11.12, Section 28).
7. The Telegram Bot must continue to use real Telegram API via long polling.
8. All mock services (Bedrock, SAP, Weather) must remain deterministic.

## OUTPUT REQUIREMENTS

Your output must include:

1. **Diagnosis Report:** A clear list of all issues found, organized by layer (A, B, C, D).
2. **Fixes Applied:** For each issue, describe what was changed and why. List every file modified.
3. **Verification Script:** The complete `06_verify_sync.py` script.
4. **Verification Results:** The output of running the verification script.
5. **Updated README_DEMO.md:** The updated documentation.
6. **Remaining Issues:** Any issues that could not be fixed automatically and require manual intervention.

## EXECUTE NOW

Perform the complete diagnosis, fix, and verification. Do not skip any step. Do not use placeholder comments. Every fix must be fully implemented.
```

