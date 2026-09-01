# -------------------------------------------------------------
# Amazon API Gateway (HTTP API v2)
# -------------------------------------------------------------

resource "aws_apigatewayv2_api" "http_api" {
  name          = "autoreplenish-http-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Api-Key"]
    max_age       = 300
  }

  tags = {
    Name = "AutoReplenish HTTP API"
  }
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/autoreplenish-${var.environment}"
  retention_in_days = 30
}

# -------------------------------------------------------------
# Integrations
# -------------------------------------------------------------

# Telegram Webhook Integration
resource "aws_apigatewayv2_integration" "telegram_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.telegram_webhook.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "telegram_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /webhook/telegram"
  target    = "integrations/${aws_apigatewayv2_integration.telegram_integration.id}"
}

resource "aws_lambda_permission" "allow_apigw_telegram" {
  statement_id  = "AllowAPIGatewayTelegramWebhook"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*/webhook/telegram"
}

# Dashboard API Integration
resource "aws_apigatewayv2_integration" "dashboard_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.dashboard_api.invoke_arn
  payload_format_version = "2.0"
}

# Dashboard API Routes
resource "aws_apigatewayv2_route" "dashboard_proxy_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /api/v1/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.dashboard_integration.id}"
}

resource "aws_lambda_permission" "allow_apigw_dashboard" {
  statement_id  = "AllowAPIGatewayDashboardApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dashboard_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*/api/v1/*"
}
