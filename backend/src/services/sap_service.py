import time
import uuid
import logging
import requests
from requests.auth import HTTPBasicAuth
import backend.src.config as config
from backend.src.models.schema import StoreProfile, SKUItem
from backend.src.services.dynamodb_service import DynamoDBService

logger = logging.getLogger("autoreplenish.sap")


class SAPService:
    def __init__(self, db_service: DynamoDBService = None):
        self.db = db_service or DynamoDBService()
        self.token_url = config.SAP_TOKEN_URL
        self.client_id = config.SAP_CLIENT_ID
        self.client_secret = config.SAP_CLIENT_SECRET
        self._cached_token = None
        self._token_expires_at = 0

    def get_access_token(self) -> str:
        """Mengambil Bearer Token resmi dari SAP BTP OAuth2 service."""
        now = time.time()
        if self._cached_token and now < self._token_expires_at:
            return self._cached_token

        if not self.token_url or not self.client_id or not self.client_secret:
            raise ValueError("Kredensial SAP BTP belum lengkap di konfigurasi environment.")

        resp = requests.post(
            self.token_url,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=(5, 10),
        )

        if resp.status_code != 200:
            logger.error("Otentikasi SAP BTP gagal dengan kode HTTP %s", resp.status_code)
            raise RuntimeError(f"Otentikasi SAP BTP ditolak (HTTP {resp.status_code}).")

        token_data = resp.json()
        self._cached_token = token_data.get("access_token")
        self._token_expires_at = now + token_data.get("expires_in", 3600) - 60
        return self._cached_token

    def verify_connection(self) -> dict:
        """Pemeriksaan kesehatan konektivitas ke SAP BTP tanpa membocorkan prefix token."""
        try:
            self.get_access_token()
            return {
                "status": "CONNECTED",
                "message": "Handshake OAuth2 SAP BTP terverifikasi",
            }
        except Exception as e:
            logger.warning("Healthcheck SAP gagal: %s", e)
            return {
                "status": "ERROR",
                "message": "Gagal memverifikasi token OAuth2 SAP BTP",
            }

    def create_purchase_requisition(
        self,
        store: StoreProfile,
        sku: SKUItem,
        quantity: int,
        idempotency_key: str,
        unit: str = "PCE",
    ) -> dict:
        """
        Menerbitkan Purchase Requisition ke SAP:
        - Mengambil harga satuan asli dari SKUItem dan kode Plant/Storage dari StoreProfile.
        - Jika endpoint OData S/4HANA live dikonfigurasi, melakukan CSRF Fetch + HTTP POST nyata.
        - Menyimpan status transaksi aktual (SAP_SUBMITTED, BTP_VERIFIED_SANDBOX_PR, atau SAP_FAILED).
        """
        # 1. Development/staging safety: never perform SAP OAuth/OData write
        # unless the deployment explicitly enables it.
        token = None
        if config.SAP_WRITE_ENABLED:
            token = self.get_access_token()

        # 2. Generate nomor referensi PR berbasis idempotency key agar tidak duplikat
        short_hash = idempotency_key[-6:].upper() if idempotency_key else uuid.uuid4().hex[:6].upper()
        pr_number = f"PR-SAP-{int(time.time())}-{short_hash}"

        # 3. Bentuk envelope payload OData dengan parameter master data toko & SKU asli
        sap_payload = {
            "d": {
                "PurchaseRequisition": pr_number,
                "PurchaseRequisitionType": "NB",
                "PurReqnDescription": f"AutoReplenish {store.store_id} - {sku.sku_name}"[:40],
                "to_PurchaseReqnItem": {
                    "results": [
                        {
                            "PurchaseRequisitionItem": "00010",
                            "Material": sku.sku_id,
                            "RequestedQuantity": str(quantity),
                            "BaseUnit": unit,
                            "Plant": store.sap_plant,
                            "StorageLocation": store.sap_storage_location,
                            "PurchasingOrganization": store.sap_purchasing_org,
                            "PurReqnPrice": f"{sku.unit_price:.2f}",
                            "Currency": sku.currency,
                        }
                    ]
                },
            }
        }

        submission_status = "SAP_DRY_RUN" if not config.SAP_WRITE_ENABLED else "BTP_VERIFIED_SANDBOX_PR"
        http_status_code = 200
        sap_response_excerpt = (
            "SAP write disabled; payload PR hanya disimpan untuk dry-run."
            if not config.SAP_WRITE_ENABLED
            else "Token OAuth2 SAP BTP valid; dokumen PR disimpan pada persistent store."
        )

        # 4. Jika toko mengaktifkan SAP_BTP dan memiliki URL OData non-sandbox yang dapat di-POST
        odata_url = (store.sap_odata_url or "").strip()
        if (
            config.SAP_WRITE_ENABLED
            and store.ingestion_mode == "SAP_BTP"
            and odata_url
            and "sandbox.api.sap.com" not in odata_url
        ):
            session = requests.Session()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            }
            try:
                # Fetch CSRF Token terlebih dahulu sesuai protokol SAP OData
                csrf_resp = session.get(
                    odata_url,
                    headers={**headers, "X-CSRF-Token": "Fetch"},
                    timeout=(5, 10),
                )
                if csrf_resp.status_code >= 400:
                    raise RuntimeError(f"SAP CSRF fetch gagal (HTTP {csrf_resp.status_code}).")
                csrf_token = csrf_resp.headers.get("X-CSRF-Token")
                if not csrf_token:
                    raise RuntimeError("SAP CSRF token tidak dikembalikan oleh endpoint.")
                headers["X-CSRF-Token"] = csrf_token

                post_resp = session.post(
                    f"{odata_url.rstrip('/')}/A_PurchaseRequisitionHeader",
                    json=sap_payload,
                    headers=headers,
                    timeout=(5, 15),
                )
                http_status_code = post_resp.status_code

                if post_resp.status_code in (200, 201):
                    submission_status = "SAP_SUBMITTED"
                    resp_json = post_resp.json().get("d", {})
                    pr_number = resp_json.get("PurchaseRequisition", pr_number)
                    sap_response_excerpt = "Berhasil dikirim ke endpoint SAP S/4HANA OData."
                else:
                    submission_status = "SAP_FAILED"
                    sap_response_excerpt = f"SAP OData menolak request (HTTP {post_resp.status_code})."
            except Exception as e:
                logger.error("Koneksi HTTP POST ke SAP OData gagal: %s", e)
                submission_status = "SAP_FAILED"
                http_status_code = 502
                sap_response_excerpt = "Gagal menghubungi server SAP OData target."

        pr_record = {
            "pr_number": pr_number,
            "idempotency_key": idempotency_key,
            "store_id": store.store_id,
            "sku_id": sku.sku_id,
            "sku_name": sku.sku_name,
            "quantity": quantity,
            "unit_price": sku.unit_price,
            "total_amount": round(quantity * sku.unit_price, 2),
            "currency": sku.currency,
            "plant": store.sap_plant,
            "storage_location": store.sap_storage_location,
            "status": submission_status,
            "http_status_code": http_status_code,
            "sap_response_note": sap_response_excerpt,
            "odata_payload": sap_payload,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.db.save_audit_log(
            store_id=store.store_id,
            timestamp_str=str(int(time.time())),
            sku_id=sku.sku_id,
            audit_data={"sap_pr": pr_record},
        )

        return pr_record
