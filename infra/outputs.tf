output "api_gateway_endpoint" {
  description = "Base URL for the AutoReplenish API Gateway"
  value       = aws_apigatewayv2_stage.default_stage.invoke_url
}

output "telegram_webhook_url" {
  description = "Full URL for Telegram Webhook registration"
  value       = "${aws_apigatewayv2_stage.default_stage.invoke_url}webhook/telegram"
}

output "dynamodb_table_arn" {
  description = "ARN of the main DynamoDB table"
  value       = aws_dynamodb_table.main_table.arn
}

output "dynamodb_table_name" {
  description = "Name of the main DynamoDB table"
  value       = aws_dynamodb_table.main_table.name
}

output "sap_dlq_arn" {
  description = "ARN of the Dead Letter Queue for SAP PR failures"
  value       = aws_sqs_queue.sap_dlq.arn
}

output "orchestrator_lambda_arn" {
  description = "ARN of the Orchestrator Lambda"
  value       = aws_lambda_function.orchestrator.arn
}
