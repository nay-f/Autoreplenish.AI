# -------------------------------------------------------------
# Common Assume Role Policy Document
# -------------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

locals {
  # Shared KMS grant needed to read/write the encrypted DynamoDB table.
  kms_statement = {
    Effect = "Allow"
    Action = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:GenerateDataKey"
    ]
    Resource = aws_kms_key.dynamo_key.arn
  }

  logging_statement = {
    Effect = "Allow"
    Action = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    Resource = "arn:aws:logs:*:*:*"
  }
}

# -------------------------------------------------------------
# 1. Orchestrator & Data Processor Lambda Role
#    DynamoDB + Bedrock + Secrets (Telegram & Weather) + SQS
# -------------------------------------------------------------
resource "aws_iam_role" "orchestrator_role" {
  name               = "AutoReplenish-OrchestratorRole-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "orchestrator_policy" {
  name        = "AutoReplenish-OrchestratorPolicy-${var.environment}"
  description = "Policy for Orchestrator Lambda: DynamoDB, Bedrock, Secrets, CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      local.logging_statement,
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.main_table.arn,
          "${aws_dynamodb_table.main_table.arn}/index/*"
        ]
      },
      local.kms_statement,
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.telegram_credentials.arn,
          aws_secretsmanager_secret.weather_credentials.arn,
          aws_secretsmanager_secret.sap_credentials.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.sap_pr_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "orchestrator_attach" {
  role       = aws_iam_role.orchestrator_role.name
  policy_arn = aws_iam_policy.orchestrator_policy.arn
}

# -------------------------------------------------------------
# 2. Telegram Webhook Lambda Role
#    DynamoDB state updates + SQS dispatch + Secrets
# -------------------------------------------------------------
resource "aws_iam_role" "telegram_webhook_role" {
  name               = "AutoReplenish-TelegramWebhookRole-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "telegram_webhook_policy" {
  name        = "AutoReplenish-TelegramWebhookPolicy-${var.environment}"
  description = "Policy for Telegram Webhook Lambda: DynamoDB state update, SQS dispatch, Secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      local.logging_statement,
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.main_table.arn,
          "${aws_dynamodb_table.main_table.arn}/index/*"
        ]
      },
      local.kms_statement,
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.telegram_credentials.arn,
          aws_secretsmanager_secret.sap_credentials.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.sap_pr_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "telegram_webhook_attach" {
  role       = aws_iam_role.telegram_webhook_role.name
  policy_arn = aws_iam_policy.telegram_webhook_policy.arn
}

# -------------------------------------------------------------
# 3. SAP Integration Worker Lambda Role
#    SQS consume + Secrets Manager + DynamoDB audit updates
# -------------------------------------------------------------
resource "aws_iam_role" "sap_worker_role" {
  name               = "AutoReplenish-SapWorkerRole-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "sap_worker_policy" {
  name        = "AutoReplenish-SapWorkerPolicy-${var.environment}"
  description = "Policy for SAP Worker: SQS, Secrets Manager, DynamoDB Transaction Ledger + Audit Log"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      local.logging_statement,
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.sap_pr_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.sap_dlq.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.sap_credentials.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.main_table.arn,
          "${aws_dynamodb_table.main_table.arn}/index/*"
        ]
      },
      local.kms_statement
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sap_worker_attach" {
  role       = aws_iam_role.sap_worker_role.name
  policy_arn = aws_iam_policy.sap_worker_policy.arn
}

# -------------------------------------------------------------
# 4. Dashboard API Lambda Role (read-only)
# -------------------------------------------------------------
resource "aws_iam_role" "dashboard_api_role" {
  name               = "AutoReplenish-DashboardApiRole-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "dashboard_api_policy" {
  name        = "AutoReplenish-DashboardApiPolicy-${var.environment}"
  description = "Policy for Dashboard API: read-only DynamoDB access (incl. GSI1/GSI2)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      local.logging_statement,
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.main_table.arn,
          "${aws_dynamodb_table.main_table.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.dynamo_key.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "dashboard_api_attach" {
  role       = aws_iam_role.dashboard_api_role.name
  policy_arn = aws_iam_policy.dashboard_api_policy.arn
}
