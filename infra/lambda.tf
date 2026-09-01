# -------------------------------------------------------------
# Lambda Function Definitions
# -------------------------------------------------------------

# Archive placeholder for terraform plan / package
data "archive_file" "backend_placeholder" {
  type        = "zip"
  output_path = "${path.module}/build/backend_pkg.zip"
  source {
    content  = "# AutoReplenish placeholder\ndef handler(event, context):\n    return {'statusCode': 200, 'body': 'OK'}\n"
    filename = "handler.py"
  }
}

# 1. Orchestrator Lambda
resource "aws_lambda_function" "orchestrator" {
  function_name    = "autoreplenish-orchestrator-${var.environment}"
  description      = "Scheduled evaluation, context aggregation, Bedrock reasoning, and Telegram notification"
  role             = aws_iam_role.orchestrator_role.arn
  runtime          = "python3.11"
  handler          = "src.handlers.scheduled_eval_handler.lambda_handler"
  filename         = data.archive_file.backend_placeholder.output_path
  source_code_hash = data.archive_file.backend_placeholder.output_base64sha256
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      ENVIRONMENT           = var.environment
      DYNAMODB_TABLE        = aws_dynamodb_table.main_table.name
      BEDROCK_MODEL_ID      = var.bedrock_model_id
      WEATHER_SECRET_NAME   = aws_secretsmanager_secret.weather_credentials.name
      TELEGRAM_SECRET_NAME  = aws_secretsmanager_secret.telegram_credentials.name
      SAP_PR_QUEUE_URL      = aws_sqs_queue.sap_pr_queue.url
      LOG_LEVEL             = "INFO"
    }
  }

  tags = {
    Component = "Orchestrator"
  }
}

# 2. Telegram Webhook Lambda
resource "aws_lambda_function" "telegram_webhook" {
  function_name    = "autoreplenish-telegram-webhook-${var.environment}"
  description      = "Handles callback actions from Store Managers via Telegram (Approve, Edit, Reject)"
  role             = aws_iam_role.telegram_webhook_role.arn
  runtime          = "python3.11"
  handler          = "src.handlers.telegram_webhook_handler.lambda_handler"
  filename         = data.archive_file.backend_placeholder.output_path
  source_code_hash = data.archive_file.backend_placeholder.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT          = var.environment
      DYNAMODB_TABLE       = aws_dynamodb_table.main_table.name
      TELEGRAM_SECRET_NAME = aws_secretsmanager_secret.telegram_credentials.name
      SAP_SECRET_NAME      = aws_secretsmanager_secret.sap_credentials.name
      SAP_PR_QUEUE_URL     = aws_sqs_queue.sap_pr_queue.url
      LOG_LEVEL            = "INFO"
    }
  }

  tags = {
    Component = "TelegramWebhook"
  }
}

# 3. SAP Integration Worker Lambda
resource "aws_lambda_function" "sap_worker" {
  function_name    = "autoreplenish-sap-worker-${var.environment}"
  description      = "Processes SAP PR creations from SQS queue and writes audit status"
  role             = aws_iam_role.sap_worker_role.arn
  runtime          = "python3.11"
  handler          = "src.handlers.sap_worker_handler.lambda_handler"
  filename         = data.archive_file.backend_placeholder.output_path
  source_code_hash = data.archive_file.backend_placeholder.output_base64sha256
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      ENVIRONMENT     = var.environment
      DYNAMODB_TABLE  = aws_dynamodb_table.main_table.name
      SAP_SECRET_NAME = aws_secretsmanager_secret.sap_credentials.name
      LOG_LEVEL       = "INFO"
    }
  }

  tags = {
    Component = "SapWorker"
  }
}

# SQS Trigger for SAP Worker
resource "aws_lambda_event_source_mapping" "sap_worker_sqs" {
  event_source_arn = aws_sqs_queue.sap_pr_queue.arn
  function_name    = aws_lambda_function.sap_worker.arn
  batch_size       = 5
  enabled          = true
}

# 4. Dashboard API Lambda
resource "aws_lambda_function" "dashboard_api" {
  function_name    = "autoreplenish-dashboard-api-${var.environment}"
  description      = "Provides REST query endpoints for React Control Center Dashboard"
  role             = aws_iam_role.dashboard_api_role.arn
  runtime          = "python3.11"
  handler          = "src.handlers.dashboard_api_handler.lambda_handler"
  filename         = data.archive_file.backend_placeholder.output_path
  source_code_hash = data.archive_file.backend_placeholder.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      DYNAMODB_TABLE = aws_dynamodb_table.main_table.name
      LOG_LEVEL      = "INFO"
    }
  }

  tags = {
    Component = "DashboardApi"
  }
}
