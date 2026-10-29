resource "aws_lambda_function" "sap_worker" {
  function_name    = "${local.name_prefix}-sap-worker"
  role             = aws_iam_role.sap_worker.arn
  handler          = "backend.lambda_handlers.sap_worker_handler"
  runtime          = "python3.12"
  filename         = var.lambda_artifact_path
  source_code_hash = filebase64sha256(var.lambda_artifact_path)
  timeout          = 240
  memory_size      = 512

  environment {
    variables = {
      ENVIRONMENT                      = var.environment
      DYNAMODB_TABLE                   = aws_dynamodb_table.core.name
      APPROVAL_QUEUE_URL               = aws_sqs_queue.approval.url
      SAP_WRITE_ENABLED                = tostring(local.sap_write)
      SECRETS_MANAGER_SECRET_ID        = aws_secretsmanager_secret.application.name
      SAP_SECRETS_MANAGER_SECRET_ID    = aws_secretsmanager_secret.sap.name
      ENABLE_LEGACY_BACKGROUND_WORKERS = "false"
    }
  }
}

resource "aws_lambda_function_event_invoke_config" "orchestrator" {
  function_name                = aws_lambda_function.orchestrator.function_name
  maximum_event_age_in_seconds = 3600
  maximum_retry_attempts       = 2

  destination_config {
    on_failure {
      destination = aws_sqs_queue.scheduler_dlq.arn
    }
  }
}

resource "aws_lambda_event_source_mapping" "sap_worker" {
  event_source_arn        = aws_sqs_queue.approval.arn
  function_name           = aws_lambda_function.sap_worker.arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
  enabled                 = true
}

resource "aws_lambda_function" "orchestrator" {
  function_name    = "${local.name_prefix}-orchestrator"
  role             = aws_iam_role.orchestrator.arn
  handler          = "backend.lambda_handlers.orchestrator_handler"
  runtime          = "python3.12"
  filename         = var.lambda_artifact_path
  source_code_hash = filebase64sha256(var.lambda_artifact_path)
  timeout          = 900
  memory_size      = 1024

  environment {
    variables = {
      ENVIRONMENT                      = var.environment
      DYNAMODB_TABLE                   = aws_dynamodb_table.core.name
      APPROVAL_QUEUE_URL               = aws_sqs_queue.approval.url
      BEDROCK_MODEL_ID                 = var.bedrock_model_id
      ALLOWED_ORIGINS                  = join(",", var.allowed_origins)
      SECRETS_MANAGER_SECRET_ID        = aws_secretsmanager_secret.application.name
      SAP_WRITE_ENABLED                = "false"
      ENABLE_LEGACY_BACKGROUND_WORKERS = "false"
    }
  }
}

resource "aws_lambda_function" "telegram_webhook" {
  function_name    = "${local.name_prefix}-telegram-webhook"
  role             = aws_iam_role.webhook.arn
  handler          = "backend.lambda_handlers.telegram_webhook_handler"
  runtime          = "python3.12"
  filename         = var.lambda_artifact_path
  source_code_hash = filebase64sha256(var.lambda_artifact_path)
  timeout          = 20
  memory_size      = 512

  environment {
    variables = {
      ENVIRONMENT                      = var.environment
      DYNAMODB_TABLE                   = aws_dynamodb_table.core.name
      APPROVAL_QUEUE_URL               = aws_sqs_queue.approval.url
      SECRETS_MANAGER_SECRET_ID        = aws_secretsmanager_secret.application.name
      ORCHESTRATOR_FUNCTION_NAME       = aws_lambda_function.orchestrator.function_name
      ALLOWED_ORIGINS                  = join(",", var.allowed_origins)
      SAP_WRITE_ENABLED                = "false"
      ENABLE_LEGACY_BACKGROUND_WORKERS = "false"
    }
  }
}

resource "aws_lambda_function" "dashboard_api" {
  function_name    = "${local.name_prefix}-dashboard-api"
  role             = aws_iam_role.dashboard.arn
  handler          = "backend.lambda_handlers.dashboard_api_handler"
  runtime          = "python3.12"
  filename         = var.lambda_artifact_path
  source_code_hash = filebase64sha256(var.lambda_artifact_path)
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      ENVIRONMENT                      = var.environment
      DYNAMODB_TABLE                   = aws_dynamodb_table.core.name
      APPROVAL_QUEUE_URL               = aws_sqs_queue.approval.url
      SECRETS_MANAGER_SECRET_ID        = aws_secretsmanager_secret.application.name
      ALLOWED_ORIGINS                  = join(",", var.allowed_origins)
      BEDROCK_MODEL_ID                 = var.bedrock_model_id
      SAP_WRITE_ENABLED                = "false"
      ENABLE_LEGACY_BACKGROUND_WORKERS = "false"
    }
  }
}

output "sap_worker_function_name" {
  value = aws_lambda_function.sap_worker.function_name
}

output "orchestrator_function_name" {
  value = aws_lambda_function.orchestrator.function_name
}

output "telegram_webhook_function_name" {
  value = aws_lambda_function.telegram_webhook.function_name
}

output "dashboard_api_function_name" {
  value = aws_lambda_function.dashboard_api.function_name
}
