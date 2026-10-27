resource "aws_cloudwatch_log_group" "sap_worker" {
  name              = "/aws/lambda/${local.name_prefix}-sap-worker"
  retention_in_days = local.is_prod ? 90 : 14
}

resource "aws_cloudwatch_log_group" "orchestrator" {
  name              = "/aws/lambda/${local.name_prefix}-orchestrator"
  retention_in_days = local.is_prod ? 90 : 14
}

resource "aws_cloudwatch_log_group" "telegram_webhook" {
  name              = "/aws/lambda/${local.name_prefix}-telegram-webhook"
  retention_in_days = local.is_prod ? 90 : 14
}

resource "aws_cloudwatch_log_group" "dashboard_api" {
  name              = "/aws/lambda/${local.name_prefix}-dashboard-api"
  retention_in_days = local.is_prod ? 90 : 14
}

resource "aws_cloudwatch_metric_alarm" "approval_dlq" {
  alarm_name          = "${local.name_prefix}-approval-dlq-not-empty"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.approval_dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "approval_queue_age" {
  alarm_name          = "${local.name_prefix}-approval-queue-age"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.approval.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = 900
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "scheduler_dlq" {
  alarm_name          = "${local.name_prefix}-scheduler-dlq-not-empty"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.scheduler_dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "sap_worker_errors" {
  alarm_name          = "${local.name_prefix}-sap-worker-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.sap_worker.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "sap_worker_throttles" {
  alarm_name          = "${local.name_prefix}-sap-worker-throttles"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.sap_worker.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "orchestrator_errors" {
  alarm_name          = "${local.name_prefix}-orchestrator-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.orchestrator.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "webhook_errors" {
  alarm_name          = "${local.name_prefix}-telegram-webhook-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.telegram_webhook.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "dashboard_errors" {
  alarm_name          = "${local.name_prefix}-dashboard-api-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.dashboard_api.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_log_metric_filter" "bedrock_fallback" {
  name           = "${local.name_prefix}-bedrock-fallback"
  log_group_name = aws_cloudwatch_log_group.orchestrator.name
  pattern        = "fallback"

  metric_transformation {
    name      = "BedrockFallback"
    namespace = "AutoReplenish/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "bedrock_fallback" {
  alarm_name          = "${local.name_prefix}-bedrock-fallback"
  namespace           = "AutoReplenish/${var.environment}"
  metric_name         = "BedrockFallback"
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

resource "aws_cloudwatch_log_metric_filter" "sap_failure" {
  name           = "${local.name_prefix}-sap-failure"
  log_group_name = aws_cloudwatch_log_group.sap_worker.name
  pattern        = "SAP_FAILED"

  metric_transformation {
    name      = "SapFailure"
    namespace = "AutoReplenish/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "sap_failure" {
  alarm_name          = "${local.name_prefix}-sap-failure"
  namespace           = "AutoReplenish/${var.environment}"
  metric_name         = "SapFailure"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}
