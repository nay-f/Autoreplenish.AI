data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# ==========================================
# 1. SAP WORKER IAM ROLE & POLICY
# ==========================================
resource "aws_iam_role" "sap_worker" {
  name               = "${local.name_prefix}-sap-worker"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "sap_worker" {
  role = aws_iam_role.sap_worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${local.name_prefix}-sap-worker:*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.approval.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:PutItem", "dynamodb:Query"]
        Resource = [aws_dynamodb_table.core.arn, "${aws_dynamodb_table.core.arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.application.arn, aws_secretsmanager_secret.sap.arn]
      }
    ]
  })
}

# ==========================================
# 2. ORCHESTRATOR IAM ROLE & POLICY
# ==========================================
resource "aws_iam_role" "orchestrator" {
  name               = "${local.name_prefix}-orchestrator"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "orchestrator" {
  role = aws_iam_role.orchestrator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${local.name_prefix}-orchestrator:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = [aws_dynamodb_table.core.arn, "${aws_dynamodb_table.core.arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.application.arn
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:ListFoundationModels", "bedrock:GetFoundationModel"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.scheduler_dlq.arn
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      }
    ]
  })
}

# ==========================================
# 3. TELEGRAM WEBHOOK IAM ROLE & POLICY
# ==========================================
resource "aws_iam_role" "webhook" {
  name               = "${local.name_prefix}-telegram-webhook"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "webhook" {
  role = aws_iam_role.webhook.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${local.name_prefix}-telegram-webhook:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = [aws_dynamodb_table.core.arn, "${aws_dynamodb_table.core.arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.approval.arn
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.orchestrator.arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.application.arn
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:ListFoundationModels", "bedrock:GetFoundationModel"]
        Resource = "*"
      }
    ]
  })
}

# ==========================================
# 4. DASHBOARD API IAM ROLE & POLICY
# ==========================================
resource "aws_iam_role" "dashboard" {
  name               = "${local.name_prefix}-dashboard-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "dashboard" {
  role = aws_iam_role.dashboard.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${local.name_prefix}-dashboard-api:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = [aws_dynamodb_table.core.arn, "${aws_dynamodb_table.core.arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.application.arn
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:ListFoundationModels", "bedrock:GetFoundationModel"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      }
    ]
  })
}

# ==========================================
# OUTPUTS
# ==========================================
output "sap_worker_role_arn" {
  value = aws_iam_role.sap_worker.arn
}

output "orchestrator_role_arn" {
  value = aws_iam_role.orchestrator.arn
}

output "webhook_role_arn" {
  value = aws_iam_role.webhook.arn
}

output "dashboard_role_arn" {
  value = aws_iam_role.dashboard.arn
}