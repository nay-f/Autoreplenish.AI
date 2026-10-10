# -------------------------------------------------------------
# Lambda deployment packaging
#
# The deployment artifact is produced by ./build.sh (or `make build`), which
# installs backend/requirements.txt into backend/build/ and copies backend/src
# alongside it. That directory becomes the root of the Lambda zip, so the
# configured handlers resolve as `src.handlers.<module>.lambda_handler`.
#
# Running `make build` (or `bash build.sh`) before apply is REQUIRED; the
# precondition below fails fast with an actionable message otherwise.
# -------------------------------------------------------------
locals {
  build_dir      = "${path.module}/../backend/build"
  lambda_zip     = "${path.module}/build/backend_pkg.zip"
  lambda_timeout = 30
  lambda_memory  = 512
}

data "archive_file" "backend_package" {
  type        = "zip"
  output_path = local.lambda_zip

  # backend/build contains src/ + vendored requirements. Excluding caches keeps
  # the artifact small and comfortably under the 50 MB direct-upload limit.
  source_dir = local.build_dir

  excludes = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.dist-info",
    "*.egg-info",
    ".pytest_cache",
  ]

  lifecycle {
    precondition {
      condition     = fileexists("${local.build_dir}/src/handlers/scheduled_eval_handler.py")
      error_message = "backend/build/src/handlers/scheduled_eval_handler.py not found. Run `bash build.sh` (or `make build`) before `terraform apply`."
    }
  }
}

# -------------------------------------------------------------
# Lambda Function Definitions
# -------------------------------------------------------------

# 1. Orchestrator Lambda (EventBridge -> reasoning -> Telegram)
resource "aws_lambda_function" "orchestrator" {
  function_name    = "autoreplenish-orchestrator-${var.environment}"
  description      = "Scheduled evaluation, context aggregation, Bedrock reasoning, and Telegram notification"
  role             = aws_iam_role.orchestrator_role.arn
  runtime          = "python3.11"
  handler          = "src.handlers.scheduled_eval_handler.lambda_handler"
  filename         = data.archive_file.backend_package.output_path
  source_code_hash = data.archive_file.backend_package.output_base64sha256
  timeout          = 60
  memory_size      = local.lambda_memory

  environment {
    variables = {
      ENVIRONMENT               = var.environment
      AWS_REGION_NAME           = var.aws_region
      DYNAMODB_TABLE            = aws_dynamodb_table.main_table.name
      BEDROCK_MODEL_ID          = var.bedrock_model_id
      WEATHER_SECRET_NAME       = aws_secretsmanager_secret.weather_credentials.name
      TELEGRAM_SECRET_NAME      = aws_secretsmanager_secret.telegram_credentials.name
      SAP_PR_QUEUE_URL          = aws_sqs_queue.sap_pr_queue.url
      WEATHER_CACHE_TTL_HOURS   = "6"
      WEATHER_CACHE_VALID_HOURS = "3"
      APPROVAL_TIMEOUT_HOURS    = "4"
      MAX_BEDROCK_RETRIES       = "2"
      LOG_LEVEL                 = "INFO"
    }
  }

  depends_on = [data.archive_file.backend_package]

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
  filename         = data.archive_file.backend_package.output_path
  source_code_hash = data.archive_file.backend_package.output_base64sha256
  timeout          = local.lambda_timeout
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

  depends_on = [data.archive_file.backend_package]

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
  filename         = data.archive_file.backend_package.output_path
  source_code_hash = data.archive_file.backend_package.output_base64sha256
  timeout          = 60
  memory_size      = local.lambda_memory

  environment {
    variables = {
      ENVIRONMENT     = var.environment
      DYNAMODB_TABLE  = aws_dynamodb_table.main_table.name
      SAP_SECRET_NAME = aws_secretsmanager_secret.sap_credentials.name
      LOG_LEVEL       = "INFO"
    }
  }

  depends_on = [data.archive_file.backend_package]

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

  # Retry transient SAP gateway blips inside the handler before the message
  # becomes visible again and is retried by SQS.
  function_response_types = ["ReportBatchItemFailures"]
}

# 4. Dashboard API Lambda
resource "aws_lambda_function" "dashboard_api" {
  function_name    = "autoreplenish-dashboard-api-${var.environment}"
  description      = "Provides REST query endpoints for React Control Center Dashboard"
  role             = aws_iam_role.dashboard_api_role.arn
  runtime          = "python3.11"
  handler          = "src.handlers.dashboard_api_handler.lambda_handler"
  filename         = data.archive_file.backend_package.output_path
  source_code_hash = data.archive_file.backend_package.output_base64sha256
  timeout          = local.lambda_timeout
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      DYNAMODB_TABLE = aws_dynamodb_table.main_table.name
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.backend_package]

  tags = {
    Component = "DashboardApi"
  }
}
