resource "aws_iam_role" "eventbridge" {
  name = "${local.name_prefix}-eventbridge"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge" {
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.orchestrator.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.scheduler_dlq.arn
      }
    ]
  })
}

resource "aws_sqs_queue" "scheduler_dlq" {
  name                      = "${local.name_prefix}-scheduler-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_scheduler_schedule" "morning" {
  count = var.enable_eventbridge ? 1 : 0
  name  = "${local.name_prefix}-03-00-wib"

  flexible_time_window { mode = "OFF" }

  schedule_expression          = "cron(0 3 * * ? *)"
  schedule_expression_timezone = "Asia/Jakarta"

  target {
    arn      = aws_lambda_function.orchestrator.arn
    role_arn = aws_iam_role.eventbridge.arn
    input    = jsonencode({ schedule = "03:00", environment = var.environment })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts        = 2
    }

    dead_letter_config {
      arn = aws_sqs_queue.scheduler_dlq.arn
    }
  }
}

resource "aws_scheduler_schedule" "afternoon" {
  count = var.enable_eventbridge ? 1 : 0
  name  = "${local.name_prefix}-14-00-wib"

  flexible_time_window { mode = "OFF" }

  schedule_expression          = "cron(0 14 * * ? *)"
  schedule_expression_timezone = "Asia/Jakarta"

  target {
    arn      = aws_lambda_function.orchestrator.arn
    role_arn = aws_iam_role.eventbridge.arn
    input    = jsonencode({ schedule = "14:00", environment = var.environment })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts        = 2
    }

    dead_letter_config {
      arn = aws_sqs_queue.scheduler_dlq.arn
    }
  }
}
