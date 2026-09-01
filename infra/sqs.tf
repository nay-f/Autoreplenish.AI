resource "aws_sqs_queue" "sap_dlq" {
  name                      = "autoreplenish-sap-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true

  tags = {
    Name = "SAP Integration DLQ"
  }
}

resource "aws_sqs_queue" "sap_pr_queue" {
  name                      = "autoreplenish-sap-pr-queue-${var.environment}"
  message_retention_seconds = 86400 # 1 day
  sqs_managed_sse_enabled   = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.sap_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "SAP Purchase Requisition Queue"
  }
}
