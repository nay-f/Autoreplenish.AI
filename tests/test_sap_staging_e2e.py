"""Opt-in SAP staging contract test.

The test is intentionally skipped unless the operator explicitly enables it.
It must never point at a production endpoint and must use a dedicated SAP test
material/plant. The actual credentials remain in the external test runner.
"""

import os

import pytest


RUN_E2E = os.getenv("RUN_SAP_STAGING_E2E", "false").lower() == "true"


@pytest.mark.skipif(not RUN_E2E, reason="Set RUN_SAP_STAGING_E2E=true for the opt-in SAP staging run")
def test_sap_staging_environment_contract():
    assert os.getenv("ENVIRONMENT") == "staging"
    assert os.getenv("SAP_STAGING_ODATA_URL", "")
    assert os.getenv("SAP_STAGING_TOKEN_URL", "")
    assert os.getenv("SAP_STAGING_CLIENT_ID", "")
    assert os.getenv("SAP_STAGING_CLIENT_SECRET", "")
    assert os.getenv("SAP_STAGING_TEST_PLANT", "")
    assert os.getenv("SAP_STAGING_TEST_MATERIAL", "")
    assert "production" not in os.getenv("SAP_STAGING_ODATA_URL", "").lower()


@pytest.mark.skipif(not RUN_E2E, reason="Set RUN_SAP_STAGING_E2E=true for the opt-in SAP sandbox run")
def test_sap_staging_sandbox_purchase_requisition():
    """Execute one real OAuth -> CSRF -> OData POST against the approved sandbox."""
    if os.getenv("SAP_STAGING_WRITE_ENABLED", "false").lower() != "true":
        pytest.skip("Set SAP_STAGING_WRITE_ENABLED=true only for an approved sandbox test")

    from types import SimpleNamespace
    from unittest.mock import Mock

    import backend.src.config as config
    from backend.src.services.sap_service import SAPService

    config.SAP_WRITE_ENABLED = True
    config.SAP_TOKEN_URL = os.environ["SAP_STAGING_TOKEN_URL"]
    config.SAP_CLIENT_ID = os.environ["SAP_STAGING_CLIENT_ID"]
    config.SAP_CLIENT_SECRET = os.environ["SAP_STAGING_CLIENT_SECRET"]

    db = Mock()
    service = SAPService(db_service=db)
    store = SimpleNamespace(
        store_id=os.getenv("SAP_STAGING_TEST_STORE", "STAGING-E2E"),
        store_name="AutoReplenish staging E2E",
        sap_plant=os.environ["SAP_STAGING_TEST_PLANT"],
        sap_storage_location=os.getenv("SAP_STAGING_TEST_STORAGE_LOCATION", ""),
        sap_purchasing_org=os.getenv("SAP_STAGING_TEST_PURCHASING_ORG", ""),
        ingestion_mode="SAP_BTP",
        sap_odata_url=os.environ["SAP_STAGING_ODATA_URL"],
    )
    sku = SimpleNamespace(
        sku_id=os.environ["SAP_STAGING_TEST_MATERIAL"],
        sku_name="Approved staging test material",
        unit_price=float(os.getenv("SAP_STAGING_TEST_UNIT_PRICE", "1")),
        currency=os.getenv("SAP_STAGING_TEST_CURRENCY", "IDR"),
    )
    result = service.create_purchase_requisition(
        store=store,
        sku=sku,
        quantity=int(os.getenv("SAP_STAGING_TEST_QUANTITY", "1")),
        idempotency_key="STAGING-E2E-REQ-1",
    )
    assert result["status"] == "SAP_SUBMITTED"
    assert result["pr_number"]
