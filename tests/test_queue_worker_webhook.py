import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from backend import lambda_handlers
from backend.src.services.approval_queue_service import ApprovalQueueService
from backend.src.services.sap_worker_service import SAPWorkerService
from backend.src.services.sap_service import SAPService


def test_queue_uses_fifo_group_and_request_deduplication():
    sqs = Mock()
    sqs.send_message.return_value = {"MessageId": "msg-1"}
    with patch("backend.src.services.approval_queue_service.boto3.client", return_value=sqs):
        with patch("backend.src.services.approval_queue_service.config.APPROVAL_QUEUE_URL", "https://sqs/approval.fifo"):
            result = ApprovalQueueService().enqueue("REQ-1", "STORE-1", "SKU-1", 12, "chat-1")

    kwargs = sqs.send_message.call_args.kwargs
    assert kwargs["MessageGroupId"] == "STORE-1"
    assert kwargs["MessageDeduplicationId"] == "REQ-1"
    assert json.loads(kwargs["MessageBody"])["schema_version"] == "1.0"
    assert result["message_id"] == "msg-1"


def test_queue_rejects_non_fifo_queue():
    with patch("backend.src.services.approval_queue_service.boto3.client", return_value=Mock()):
        with patch("backend.src.services.approval_queue_service.config.APPROVAL_QUEUE_URL", "https://sqs/standard"):
            with pytest.raises(RuntimeError, match="FIFO"):
                ApprovalQueueService().enqueue("REQ-1", "STORE-1", "SKU-1", 12, "chat-1")


def _state(status="ENQUEUED"):
    return SimpleNamespace(
        request_id="REQ-1",
        store_id="STORE-1",
        sku_id="SKU-1",
        sku_name="SKU One",
        final_qty=None,
        recommended_qty=12,
        status=status,
    )


def test_worker_replay_after_success_is_idempotent():
    db = Mock()
    db.get_approval_state.side_effect = [_state("SAP_SUBMITTED"), _state("SAP_SUBMITTED")]
    sap = Mock()
    worker = SAPWorkerService(db=db, sap=sap)

    result = worker.process(
        {"request_id": "REQ-1", "quantity": 12, "environment": "development"},
        lambda *_: (SimpleNamespace(store_id="STORE-1"), SimpleNamespace(sku_id="SKU-1")),
    )

    assert result == {"request_id": "REQ-1", "status": "SAP_SUBMITTED", "duplicate": True}
    sap.create_purchase_requisition.assert_not_called()


def test_worker_dry_run_failure_does_not_call_sap_network_write():
    db = Mock()
    db.get_approval_state.return_value = _state("ENQUEUED")
    db.transition_approval_state.side_effect = [True, True]
    sap = Mock()
    sap.create_purchase_requisition.return_value = {
        "status": "SAP_DRY_RUN",
        "pr_number": "PR-DRY-1",
    }
    worker = SAPWorkerService(db=db, sap=sap)

    result = worker.process(
        {"request_id": "REQ-1", "quantity": 12, "environment": "development"},
        lambda *_: (SimpleNamespace(store_id="STORE-1"), SimpleNamespace(sku_id="SKU-1")),
    )

    assert result["status"] == "SAP_DRY_RUN"
    assert sap.create_purchase_requisition.call_count == 1
    assert db.transition_approval_state.call_args_list[-1].kwargs["new_status"] == "SAP_DRY_RUN"


def test_worker_failure_transitions_to_sap_failed_for_retry():
    db = Mock()
    db.get_approval_state.return_value = _state("ENQUEUED")
    db.transition_approval_state.side_effect = [True, True]
    sap = Mock()
    sap.create_purchase_requisition.side_effect = TimeoutError("SAP timeout")
    worker = SAPWorkerService(db=db, sap=sap)

    with pytest.raises(TimeoutError):
        worker.process(
            {"request_id": "REQ-1", "quantity": 12, "environment": "development"},
            lambda *_: (SimpleNamespace(store_id="STORE-1"), SimpleNamespace(sku_id="SKU-1")),
        )

    assert db.transition_approval_state.call_args_list[-1].kwargs["new_status"] == "SAP_FAILED"


def test_sap_dry_run_does_not_request_oauth_or_post():
    db = Mock()
    service = SAPService(db_service=db)
    store = SimpleNamespace(
        store_id="STORE-1",
        store_name="Store One",
        sap_plant="1000",
        sap_storage_location="WH01",
        sap_purchasing_org="1000",
        ingestion_mode="SAP_BTP",
        sap_odata_url="https://sandbox.example/odata",
    )
    sku = SimpleNamespace(
        sku_id="SKU-1",
        sku_name="SKU One",
        unit_price=10.0,
        currency="IDR",
    )
    with patch("backend.src.services.sap_service.config.SAP_WRITE_ENABLED", False):
        with patch.object(service, "get_access_token") as token:
            result = service.create_purchase_requisition(store, sku, 12, "REQ-1")

    assert result["status"] == "SAP_DRY_RUN"
    token.assert_not_called()
    db.save_audit_log.assert_called_once()


def test_worker_rejects_cross_environment_message():
    db = Mock()
    worker = SAPWorkerService(db=db, sap=Mock())
    with pytest.raises(ValueError, match="environment"):
        worker.process(
            {"request_id": "REQ-1", "quantity": 12, "environment": "production"},
            lambda *_: (None, None),
        )


def test_webhook_rejects_missing_or_wrong_secret(monkeypatch):
    monkeypatch.setattr(lambda_handlers.config, "ENVIRONMENT", "staging")
    monkeypatch.setattr(lambda_handlers.config, "TELEGRAM_WEBHOOK_SECRET", "expected")
    event = {"headers": {}, "body": "{}"}
    assert lambda_handlers.telegram_webhook_handler(event, None)["statusCode"] == 401

    event["headers"] = {"X-Telegram-Bot-Api-Secret-Token": "wrong"}
    assert lambda_handlers.telegram_webhook_handler(event, None)["statusCode"] == 401


def test_webhook_validates_size_and_json_before_dispatch(monkeypatch):
    monkeypatch.setattr(lambda_handlers.config, "ENVIRONMENT", "staging")
    monkeypatch.setattr(lambda_handlers.config, "TELEGRAM_WEBHOOK_SECRET", "expected")
    headers = {"x-telegram-bot-api-secret-token": "expected"}

    assert lambda_handlers.telegram_webhook_handler(
        {"headers": headers, "body": "not-json"}, None
    )["statusCode"] == 400
    assert lambda_handlers.telegram_webhook_handler(
        {"headers": headers, "body": "x" * (lambda_handlers.MAX_WEBHOOK_BODY_BYTES + 1)}, None
    )["statusCode"] == 413


def test_webhook_dispatches_short_update_without_long_running_evaluation(monkeypatch):
    monkeypatch.setattr(lambda_handlers.config, "ENVIRONMENT", "staging")
    monkeypatch.setattr(lambda_handlers.config, "TELEGRAM_WEBHOOK_SECRET", "expected")
    handler = Mock()
    with patch("backend.main.handle_telegram_update", handler):
        response = lambda_handlers.telegram_webhook_handler(
            {
                "headers": {"x-telegram-bot-api-secret-token": "expected"},
                "body": json.dumps({"update_id": 1}),
            },
            None,
        )

    assert response["statusCode"] == 200
    handler.assert_called_once_with({"update_id": 1}, allow_long_running=False)
