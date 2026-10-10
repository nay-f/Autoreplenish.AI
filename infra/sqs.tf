# -------------------------------------------------------------
# SQS: Purchase Requisition work queue + Dead Letter Queue
# FIFO is used so that MessageDeduplicationId = request_id on the producer side
# gives transport-level protection against duplicate PR creation (PRD 14.2).
# -------------------------------------------------------------

resource "aws_sqs_queue" "sap_dlq" {
  name                        = "autoreplenish-sap-dlq-${var.environment}.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  message_retention_seconds   = 1209600 # 14 days
  sqs_managed_sse_enabled     = true

  tags = {
    Name = "SAP Integration DLQ"
  }
}

resource "aws_sqs_queue" "sap_pr_queue" {
  name                        = "autoreplenish-sap-pr-queue-${var.environment}.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  message_retention_seconds   = 86400 # 1 day
  receive_wait_time_seconds   = 10    # long polling: fewer empty receives, lower cost
  sqs_managed_sse_enabled     = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.sap_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "SAP Purchase Requisition Queue"
  }
}
