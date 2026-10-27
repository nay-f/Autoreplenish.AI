from types import SimpleNamespace
from unittest.mock import Mock

from backend.src.services.dynamodb_service import DynamoDBService


def test_conditional_approval_allows_one_actor_and_rejects_duplicate():
    db = DynamoDBService.__new__(DynamoDBService)
    table = Mock()
    db.table = table
    table.update_item.side_effect = [None, _conditional_failure()]

    first = db.transition_approval_state(
        "REQ-1", ["PENDING_APPROVAL"], "APPROVED", final_qty=12
    )
    second = db.transition_approval_state(
        "REQ-1", ["PENDING_APPROVAL"], "APPROVED", final_qty=12
    )

    assert first is True
    assert second is False
    assert table.update_item.call_count == 2


def _conditional_failure():
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
        "UpdateItem",
    )
