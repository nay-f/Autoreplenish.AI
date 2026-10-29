"""Durable approval-to-SAP queue adapter.

The webhook records approval and sends this message. SAP I/O is performed by a
separate SQS worker, so Telegram retries cannot synchronously create a document.
"""

import json
import logging
import boto3
import backend.src.config as config

logger = logging.getLogger("autoreplenish.approval_queue")


class ApprovalQueueService:
    def __init__(self):
        self.queue_url = config.APPROVAL_QUEUE_URL
        self.client = boto3.client(
            "sqs",
            region_name=config.AWS_REGION,
        )

    def enqueue(
        self,
        request_id: str,
        store_id: str,
        sku_id: str,
        quantity: int,
        actor: str,
        chat_id: str = "",
        message_id: int = None,
    ) -> dict:
        if not self.queue_url:
            raise RuntimeError("APPROVAL_QUEUE_URL belum dikonfigurasi; approval ditahan.")
        if not self.queue_url.endswith(".fifo"):
            raise RuntimeError("APPROVAL_QUEUE_URL harus menunjuk ke SQS FIFO queue.")
        body = {
            "request_id": request_id,
            "store_id": store_id,
            "sku_id": sku_id,
            "quantity": quantity,
            "actor": actor,
            "chat_id": str(chat_id or ""),
            "message_id": message_id,
            "environment": config.ENVIRONMENT,
            "correlation_id": request_id,
            "schema_version": "1.0",
        }
        response = self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(body),
            MessageGroupId=store_id,
            MessageDeduplicationId=request_id,
        )
        return {"message_id": response["MessageId"], "request_id": request_id}
