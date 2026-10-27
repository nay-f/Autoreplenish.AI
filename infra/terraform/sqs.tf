resource "aws_sqs_queue" "approval_dlq" {
  name                        = "${local.name_prefix}-approval-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = 1209600
  sqs_managed_sse_enabled     = true

}

resource "aws_sqs_queue" "approval" {
  name                        = "${local.name_prefix}-approval.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  visibility_timeout_seconds  = 300
  message_retention_seconds   = 345600
  sqs_managed_sse_enabled     = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.approval_dlq.arn
    maxReceiveCount     = 5
  })
}
