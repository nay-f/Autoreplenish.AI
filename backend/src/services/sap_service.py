"""SAP S/4HANA OData Integration Service — dual-mode (LIVE / PERSISTENT SANDBOX).

Implements PRD Section 11.9, 14.1, and 14.2.

Mode resolution
---------------
**LIVE** — used when Secrets Manager actually contains SAP credentials
(``client_id``, ``client_secret`` and ``odata_base_url``). Executes the real
SAP gateway flow:
    1. OAuth2 client-credentials token request against ``token_url``.
    2. ``X-CSRF-Token: Fetch`` GET on the service root to obtain a CSRF token
       and session cookie.
    3. ``POST`` of the deep-insert Purchase Requisition payload to
       ``API_PURCHASEREQ_PROCESS_SRV`` with 5s timeout and exponential backoff
       (max 3 attempts, PRD 14.1).

**PERSISTENT SANDBOX** — automatically engaged when no SAP credentials are
configured. Returns a response with the *exact* OData ``{"d": {...}}`` envelope
of ``API_PURCHASEREQ_PROCESS_SRV``, but the PR record and the full transaction
ledger are written to **DynamoDB** (not process memory), which means
idempotency survives Lambda cold starts. This is what makes the system
runnable end-to-end today with a live Telegram bot but no S/4HANA system.

Both modes share the same idempotency contract: the ledger is consulted before
any mutation, so a double-clicked button or retried SQS message can never
produce a duplicate Purchase Requisition (PRD 14.2).
"""

import base64
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import requests
from botocore.exceptions import BotoCoreError, ClientError

from ..config import logger, SAP_SECRET_NAME, get_env
from ..models.schema import (
    SapPRItem,
    SapPRPayload,
    SapPRResponse,
    SapTransactionRecord,
)
from .dynamodb_service import DynamoDBService
from .secrets_service import SecretManagerService

MODE_LIVE = "LIVE"
MODE_SANDBOX = "PERSISTENT_SANDBOX"

HTTP_TIMEOUT_SECONDS = 5
MAX_RETRIES = 3
TOKEN_TTL_BUFFER_SECONDS = 60


class SapIntegrationService:
    """Handles communication with SAP S/4HANA MM OData APIs."""

    def __init__(
        self,
        db_service: Optional[DynamoDBService] = None,
        secret_service: Optional[SecretManagerService] = None,
        http_client: Optional[Any] = None,
        mode: Optional[str] = None,
    ):
        """
        Args:
            db_service: DynamoDB accessor for the transaction ledger / idempotency.
            secret_service: Injectable SecretManagerService (for tests).
            http_client: Injectable requests-like object (for tests).
            mode: Force ``LIVE`` or ``PERSISTENT_SANDBOX`` (tests / overrides).
        """
        self.db = db_service if db_service is not None else DynamoDBService()
        self._secret_service = secret_service
        self._http = http_client or requests
        self._mode_override = mode

        self._token_cache: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._csrf_token: Optional[str] = None
        self._csrf_cookie: Optional[str] = None
        self._csrf_expires_at: float = 0.0

        self._credentials = self._load_credentials()
        self.mode = self._resolve_mode()

    # ---------------------------------------------------------
    # Mode & credentials
    # ---------------------------------------------------------
    def _load_credentials(self) -> Dict[str, Any]:
        if self._secret_service is None:
            self._secret_service = SecretManagerService()
        try:
            return self._secret_service.get_sap_credentials(SAP_SECRET_NAME)
        except Exception as e:
            logger.error(f"Unable to resolve SAP credentials: {e}")
            return {}

    def _resolve_mode(self) -> str:
        if self._mode_override:
            return self._mode_override
        if SecretManagerService.has_live_credentials(self._credentials):
            logger.info("SAP integration running in LIVE mode (S/4HANA OData)")
            return MODE_LIVE
        logger.info(
            "SAP integration running in PERSISTENT_SANDBOX mode "
            "(no SAP credentials configured; PR ledger persisted to DynamoDB)"
        )
        return MODE_SANDBOX

    @property
    def is_live(self) -> bool:
        return self.mode == MODE_LIVE

    def get_connection_status(self) -> Dict[str, Any]:
        """Report the SAP linkage for the dashboard SAP Monitor."""
        txns = self.db.list_sap_transactions(limit=500)
        successful = [t for t in txns if t.status == "SUCCESS"]
        failed = [t for t in txns if t.status == "FAILED"]
        attempts = len(successful) + len(failed)

        return {
            "mode": self.mode,
            "connection_status": "ONLINE" if self.is_live else "SANDBOX",
            "sap_host": self._odata_host(),
            "odata_endpoint": self._odata_path(),
            "authenticated": self.is_live and self._token_cache is not None,
            "metrics": {
                "total_pr_generated": len(successful),
                "total_pr_failed": len(failed),
                "success_rate_pct": round(len(successful) / attempts * 100.0, 2) if attempts else 100.0,
                "dlq_message_count": len(failed),
            },
            "recent_transactions": [
                {
                    "request_id": t.request_id,
                    "store_id": t.store_id,
                    "sku_id": t.sku_id,
                    "quantity": t.quantity,
                    "sap_pr_id": t.sap_pr_id,
                    "status": t.status,
                    "mode": t.mode,
                    "timestamp": t.created_at,
                    "error_message": t.error_message,
                }
                for t in txns[:25]
            ],
        }

    def _odata_host(self) -> str:
        base = self._credentials.get("odata_base_url") or get_env(
            "SAP_ODATA_BASE_URL", "https://sap-sandbox.local:44300"
        )
        return base.split("/sap/")[0]

    def _odata_path(self) -> str:
        base = self._credentials.get("odata_base_url") or get_env(
            "SAP_ODATA_BASE_URL", "/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV"
        )
        if base.startswith("http"):
            base = base.split("://", 1)[1]
            base = "/" + base.split("/", 1)[1] if "/" in base else base
        return base or "/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV"

    # ---------------------------------------------------------
    # OAuth2 / CSRF (LIVE only)
    # ---------------------------------------------------------
    def get_access_token(self) -> str:
        """Fetch (or reuse) an OAuth2 access token for the SAP gateway."""
        if self._token_cache and time.time() < self._token_expires_at:
            return self._token_cache

        if not self.is_live:
            # Sandbox mode: deterministic, clearly-labelled placeholder token.
            self._token_cache = f"sandbox_bearer_token_{uuid.uuid4().hex[:12]}"
            self._token_expires_at = time.time() + 3600
            return self._token_cache

        creds = self._credentials
        token_url = creds.get("token_url")
        if not token_url:
            raise RuntimeError("SAP token_url is not configured; cannot obtain a LIVE access token")

        basic = base64.b64encode(
            f"{creds['client_id']}:{creds['client_secret']}".encode("utf-8")
        ).decode("ascii")

        headers = {
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._http.post(
                    token_url,
                    headers=headers,
                    data=payload,
                    timeout=HTTP_TIMEOUT_SECONDS,
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"SAP token endpoint returned HTTP {resp.status_code}")
                data = resp.json()
                access_token = data.get("access_token")
                if not access_token:
                    raise ValueError("SAP token response did not contain access_token")
                self._token_cache = access_token
                expires_in = int(data.get("expires_in", 3600))
                self._token_expires_at = time.time() + max(0, expires_in - TOKEN_TTL_BUFFER_SECONDS)
                logger.info("SAP OAuth2 access token acquired")
                return access_token
            except Exception as e:
                last_error = e
                logger.warning(f"SAP token request attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt - 1))

        raise RuntimeError(f"Unable to obtain SAP access token: {last_error}")

    def _get_csrf_token(self) -> Dict[str, str]:
        """Fetch a CSRF token + session cookie from the SAP gateway."""
        if self._csrf_token and time.time() < self._csrf_expires_at:
            return {"token": self._csrf_token, "cookie": self._csrf_cookie or ""}

        if not self.is_live:
            self._csrf_token = f"SANDBOX-CSRF-{uuid.uuid4().hex[:16]}"
            self._csrf_cookie = f"SAP_SESSIONID=SBX_{uuid.uuid4().hex[:10]}"
            self._csrf_expires_at = time.time() + 1800
            return {"token": self._csrf_token, "cookie": self._csrf_cookie}

        creds = self._credentials
        base_url = creds.get("odata_base_url", "")
        try:
            resp = self._http.get(
                base_url.rstrip("/"),
                headers={
                    "X-CSRF-Token": "Fetch",
                    "Authorization": f"Bearer {self.get_access_token()}",
                    "x-sap-client": creds.get("sap_client", "100"),
                    "Accept": "application/json",
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except Exception as e:
            raise RuntimeError(f"Unable to fetch SAP CSRF token: {e}")

        if resp.status_code >= 400:
            raise RuntimeError(f"CSRF fetch returned HTTP {resp.status_code}")

        token = resp.headers.get("x-csrf-token")
        if not token:
            raise ValueError("SAP gateway did not return an x-csrf-token header")

        self._csrf_token = token
        self._csrf_cookie = resp.headers.get("set-cookie", "")
        self._csrf_expires_at = time.time() + 1800
        logger.info("SAP CSRF token acquired")
        return {"token": token, "cookie": self._csrf_cookie}

    # ---------------------------------------------------------
    # Payload construction (PRD 11.9)
    # ---------------------------------------------------------
    def build_pr_payload(
        self,
        sku_id: str,
        sku_name: str,
        quantity: int,
        plant: str = "1000",
        storage_location: str = "STR-ALMADINA-001",
        base_unit: str = "PCS",
        delivery_lead_days: int = 2
    ) -> SapPRPayload:
        """Construct a standard OData Purchase Requisition deep-insert payload."""
        delivery_date = (
            datetime.now(timezone.utc) + timedelta(days=max(1, delivery_lead_days))
        ).strftime("%Y-%m-%d")

        item = SapPRItem(
            Material=sku_id,
            Plant=plant,
            StoreLocation=storage_location,
            RequestedQuantity=quantity,
            BaseUnit=base_unit,
            DeliveryDate=delivery_date,
            ShortText=f"AutoReplenish.ai - {sku_name}"
        )
        return SapPRPayload(
            PurchaseRequisitionType="NB",
            PurchaseRequisitionItems=[item]
        )

    # ---------------------------------------------------------
    # Purchase Requisition creation (both modes)
    # ---------------------------------------------------------
    def create_purchase_requisition(
        self,
        request_id: str,
        payload: SapPRPayload,
        store_id: str = "STR-ALMADINA-001"
    ) -> SapPRResponse:
        """Create a PR in SAP S/4HANA with DynamoDB-backed idempotency.

        PRD 14.2: "Cek status DynamoDB sebelum POST" — the ledger is the single
        source of truth for whether a PR already exists for ``request_id``.
        """
        # 1. Idempotency check against the persistent ledger (survives cold starts)
        existing = self.db.get_sap_transaction(request_id)
        if existing and existing.status == "SUCCESS":
            logger.info(
                f"Idempotency hit (ledger): PR already created for request {request_id} "
                f"-> {existing.sap_pr_id}"
            )
            return SapPRResponse(
                success=True,
                sap_pr_id=existing.sap_pr_id,
                status_code=200,
                timestamp=existing.created_at,
                mode=existing.mode,
                odata_response=existing.response_payload,
            )

        # 2. Dispatch by mode
        if self.is_live:
            response = self._create_pr_live(request_id, payload, store_id)
        else:
            response = self._create_pr_sandbox(request_id, payload, store_id)

        # 3. Persist the ledger entry regardless of outcome
        self._persist_transaction(
            request_id=request_id,
            store_id=store_id,
            payload=payload,
            response=response,
        )
        return response

    # ---------------------------------------------------------
    # LIVE mode: real OData POST
    # ---------------------------------------------------------
    def _create_pr_live(
        self,
        request_id: str,
        payload: SapPRPayload,
        store_id: str
    ) -> SapPRResponse:
        base_url = self._credentials.get("odata_base_url", "").rstrip("/")
        url = f"{base_url}/A_PurchaseRequisitionHeader"
        csrf = self._get_csrf_token()

        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "X-CSRF-Token": csrf["token"],
            "x-sap-client": self._credentials.get("sap_client", "100"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if csrf.get("cookie"):
            headers["Cookie"] = csrf["cookie"]

        last_error: Optional[str] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._http.post(
                    url,
                    headers=headers,
                    json=payload.to_dict(),
                    timeout=HTTP_TIMEOUT_SECONDS,
                )
                status_code = resp.status_code

                if status_code in (200, 201):
                    body = self._safe_json(resp)
                    pr_id = self._extract_pr_id(body, resp)
                    logger.info(f"SAP PR created LIVE: {pr_id} for request {request_id}")
                    return SapPRResponse(
                        success=True,
                        sap_pr_id=pr_id,
                        status_code=status_code,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        mode=MODE_LIVE,
                        odata_response=body,
                    )

                # 4xx are deterministic rejections: retrying cannot help.
                if 400 <= status_code < 500:
                    logger.error(f"SAP rejected PR for {request_id}: HTTP {status_code}")
                    return SapPRResponse(
                        success=False,
                        error_message=f"SAP OData rejected the payload (HTTP {status_code}): {resp.text[:300]}",
                        status_code=status_code,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        mode=MODE_LIVE,
                    )

                last_error = f"HTTP {status_code}"

            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"

            logger.warning(f"SAP POST attempt {attempt}/{MAX_RETRIES} for {request_id} failed: {last_error}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt - 1))

        return SapPRResponse(
            success=False,
            error_message=f"SAP S/4HANA OData Gateway unreachable after {MAX_RETRIES} attempts: {last_error}",
            status_code=503,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=MODE_LIVE,
        )

    @staticmethod
    def _safe_json(resp: Any) -> Dict[str, Any]:
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {"d": data}
        except Exception:
            return {}

    def _extract_pr_id(self, body: Dict[str, Any], resp: Any = None) -> str:
        """Resolve the PR number from the SAP response body, or the location header."""
        candidates: List[Any] = []
        d = body.get("d") if isinstance(body, dict) else None
        if isinstance(d, dict):
            candidates.extend([
                d.get("PurchaseRequisition"),
                (d.get("PurchaseRequisitionHeader") or {}).get("PurchaseRequisition")
                if isinstance(d.get("PurchaseRequisitionHeader"), dict) else None,
            ])
        if resp is not None:
            location = resp.headers.get("location") or ""
            if "(" in location and ")" in location:
                candidates.append(location.split("(", 1)[1].split(")", 1)[0].strip("'"))

        for candidate in candidates:
            if candidate:
                # SAP PR numbers are character fields with significant leading
                # zeros ("0014500019999"), so never strip them.
                return str(candidate).strip()

        # Last resort: use our own monotonic sequence (already allocated).
        return self._format_pr_number(self.db.next_sap_pr_sequence())

    # ---------------------------------------------------------
    # SANDBOX mode: deterministic, SAP-shaped, DynamoDB-persisted
    # ---------------------------------------------------------
    def _create_pr_sandbox(
        self,
        request_id: str,
        payload: SapPRPayload,
        store_id: str
    ) -> SapPRResponse:
        """Emit a PR identical in shape to the SAP OData V2 response.

        The PR number comes from a DynamoDB atomic counter so it remains
        monotonic and unique across invocations and containers.
        """
        sequence = self.db.next_sap_pr_sequence()
        pr_number = self._format_pr_number(sequence)
        now_str = datetime.now(timezone.utc).isoformat()

        odata_response = {
            "d": {
                "PurchaseRequisition": pr_number,
                "PurchaseRequisitionType": payload.PurchaseRequisitionType,
                "CreationDate": now_str,
                "CreatedByUser": "AUTOREPLENISH_AGENT",
                "Plant": payload.PurchaseRequisitionItems[0].Plant if payload.PurchaseRequisitionItems else "",
                "AutoReplenishRequestId": request_id,
                "ToPurchaseReqnItem": [
                    dict(item.to_dict()) for item in payload.PurchaseRequisitionItems
                ],
            }
        }

        logger.info(
            f"SAP PR created [PERSISTENT_SANDBOX]: {pr_number} for request {request_id} "
            f"(ledger written to DynamoDB)"
        )
        return SapPRResponse(
            success=True,
            sap_pr_id=pr_number,
            status_code=201,
            timestamp=now_str,
            mode=MODE_SANDBOX,
            odata_response=odata_response,
        )

    @staticmethod
    def _format_pr_number(sequence: int) -> str:
        """Format a sequence into the standard 10-character SAP PR number."""
        return f"001{sequence % 10_000_000:07d}"

    # ---------------------------------------------------------
    # Transaction ledger
    # ---------------------------------------------------------
    def _persist_transaction(
        self,
        request_id: str,
        payload: SapPRPayload,
        response: SapPRResponse,
        store_id: str
    ) -> SapTransactionRecord:
        txn = SapTransactionRecord(
            request_id=request_id,
            store_id=store_id,
            sku_id=payload.PurchaseRequisitionItems[0].Material if payload.PurchaseRequisitionItems else "",
            quantity=payload.PurchaseRequisitionItems[0].RequestedQuantity if payload.PurchaseRequisitionItems else 0,
            status="SUCCESS" if response.success else "FAILED",
            sap_pr_id=response.sap_pr_id,
            mode=response.mode,
            created_at=response.timestamp or datetime.now(timezone.utc).isoformat(),
            response_payload=response.odata_response,
            error_message=response.error_message,
            status_code=response.status_code,
        )
        try:
            self.db.put_sap_transaction(txn)
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to write SAP transaction ledger for {request_id}: {e}")
        return txn
