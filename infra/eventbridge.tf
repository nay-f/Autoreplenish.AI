# -------------------------------------------------------------
# EventBridge Rules for Stock Evaluation Schedule
# -------------------------------------------------------------

# 1. Morning Evaluation: 05:00 WIB (22:00 UTC previous day)
resource "aws_cloudwatch_event_rule" "morning_evaluation" {
  name                = "autoreplenish-morning-eval-${var.environment}"
  description         = "Triggers 05:00 WIB stock replenishment evaluation"
  schedule_expression = var.morning_schedule_cron
  state               = "ENABLED"

  tags = {
    Schedule = "Morning-0500WIB"
  }
}

resource "aws_cloudwatch_event_target" "morning_target" {
  rule      = aws_cloudwatch_event_rule.morning_evaluation.name
  target_id = "AutoReplenish-MorningOrchestrator"
  arn       = aws_lambda_function.orchestrator.arn

  input = jsonencode({
    trigger_source = "EVENTBRIDGE_SCHEDULED"
    schedule_slot  = "MORNING_0500"
    batch_limit    = 50
  })
}

resource "aws_lambda_permission" "allow_eventbridge_morning" {
  statement_id  = "AllowExecutionFromEventBridgeMorning"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orchestrator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.morning_evaluation.arn
}

# 2. Afternoon Evaluation: 14:00 WIB (07:00 UTC)
resource "aws_cloudwatch_event_rule" "afternoon_evaluation" {
  name                = "autoreplenish-afternoon-eval-${var.environment}"
  description         = "Triggers 14:00 WIB stock replenishment evaluation"
  schedule_expression = var.afternoon_schedule_cron
  state               = "ENABLED"

  tags = {
    Schedule = "Afternoon-1400WIB"
  }
}

resource "aws_cloudwatch_event_target" "afternoon_target" {
  rule      = aws_cloudwatch_event_rule.afternoon_evaluation.name
  target_id = "AutoReplenish-AfternoonOrchestrator"
  arn       = aws_lambda_function.orchestrator.arn

  input = jsonencode({
    trigger_source = "EVENTBRIDGE_SCHEDULED"
    schedule_slot  = "AFTERNOON_1400"
    batch_limit    = 50
  })
}

resource "aws_lambda_permission" "allow_eventbridge_afternoon" {
  statement_id  = "AllowExecutionFromEventBridgeAfternoon"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orchestrator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.afternoon_evaluation.arn
}
