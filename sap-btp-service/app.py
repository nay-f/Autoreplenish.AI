import os
import time
import uuid
import requests
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)
PR_LEDGER = []

def call_sap_rpt(material: str, qty: float, price: float) -> dict:
    """Memanggil model tabular SAP RPT-1.6 di SAP AI Core."""
    ai_url = os.environ.get("AICORE_API_URL")
    auth_url = os.environ.get("AICORE_AUTH_URL")
    cid = os.environ.get("AICORE_CLIENT_ID")
    csec = os.environ.get("AICORE_CLIENT_SECRET")
    if not (ai_url and auth_url and cid and csec):
        return {"status": "SKIPPED"}
    try:
        tok = requests.post(
            f"{auth_url}/oauth/token",
            auth=(cid, csec),
            data={"grant_type": "client_credentials"},
            timeout=4
        ).json().get("access_token")
        payload = {
            "prediction_config": {
                "target_columns": [{"name": "RECOMMENDED_QTY", "prediction_placeholder": "[PREDICT]", "task_type": "regression"}]
            },
            "index_column": "ID",
            "rows": [
                {"ID": "1", "MATERIAL": material, "PRICE": float(price or 10000), "RECOMMENDED_QTY": "[PREDICT]"},
                {"ID": "2", "MATERIAL": "SKU-PILOT-001", "PRICE": 34000.0, "RECOMMENDED_QTY": 36.0},
                {"ID": "3", "MATERIAL": "SKU-PILOT-002", "PRICE": 22000.0, "RECOMMENDED_QTY": 12.0}
            ]
        }
        r = requests.post(
            f"{ai_url}/v2/inference/deployments/d76cf689a05d504f/predict",
            headers={"Authorization": f"Bearer {tok}", "AI-Resource-Group": "default", "Content-Type": "application/json"},
            json=payload,
            timeout=5
        )
        return {"model": "sap-rpt-1.6", "deployment": "d76cf689a05d504f", "http_status": r.status_code}
    except Exception as e:
        return {"model": "sap-rpt-1.6", "note": str(e)}

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "AutoReplenish.ai - SAP BTP S/4HANA OData & AI Core Hub",
        "org": "SEAIO_aws-sap-hackathon-si4ykj9d",
        "space": "hackathon-autoreplenish-ai",
        "total_pr_submitted": len(PR_LEDGER),
        "purchase_requisitions": PR_LEDGER
    })

@app.route("/odata/s4hana", methods=["GET", "HEAD"])
def fetch_csrf():
    token = f"sap-csrf-{uuid.uuid4().hex}"
    resp = make_response(jsonify({"d": {"EntitySets": ["A_PurchaseRequisitionHeader"]}}), 200)
    resp.headers["X-CSRF-Token"] = token
    return resp

@app.route("/odata/s4hana/A_PurchaseRequisitionHeader", methods=["POST"])
def create_pr_header():
    body = request.get_json(silent=True) or {}
    d_obj = body.get("d", body)
    pr_number = d_obj.get("PurchaseRequisition") or f"PR-SAP-{int(time.time())}"
    items = d_obj.get("to_PurchaseReqnItem", {}).get("results", [{}])
    first_item = items[0] if items else {}

    material = first_item.get("Material", "UNKNOWN")
    qty = float(first_item.get("RequestedQuantity", 0))
    price = float(first_item.get("PurReqnPrice", 0))

    rpt_info = call_sap_rpt(material, qty, price)

    record = {
        "PurchaseRequisition": pr_number,
        "PurchaseRequisitionType": d_obj.get("PurchaseRequisitionType", "NB"),
        "PurReqnDescription": d_obj.get("PurReqnDescription", ""),
        "Material": material,
        "RequestedQuantity": str(int(qty)),
        "Plant": first_item.get("Plant", "1000"),
        "StorageLocation": first_item.get("StorageLocation", "0001"),
        "PurchasingOrganization": first_item.get("PurchasingOrganization", "1000"),
        "PurReqnPrice": str(price),
        "Currency": first_item.get("Currency", "IDR"),
        "SAP_AI_Core": rpt_info,
        "CreatedAt": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }
    PR_LEDGER.insert(0, record)
    return jsonify({"d": record}), 201
