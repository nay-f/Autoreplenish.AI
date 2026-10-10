# -------------------------------------------------------------
# AWS Secrets Manager
# Values come from sensitive Terraform variables and are NOT committed.
# `ignore_changes` on secret_string means that once a real value is written
# (via terraform apply with a tfvars file, or the AWS console/CLI), subsequent
# applies will not silently revert it to a placeholder (PRD 24: no hardcoded secrets).
# -------------------------------------------------------------

resource "aws_secretsmanager_secret" "sap_credentials" {
  name                    = "autoreplenish/sap-credentials-${var.environment}"
  description             = "SAP S/4HANA OData API credentials and endpoints (empty => PERSISTENT_SANDBOX mode)"
  recovery_window_in_days = 0

  tags = {
    Name = "SAP S/4HANA Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "sap_credentials_val" {
  secret_id = aws_secretsmanager_secret.sap_credentials.id

  secret_string = jsonencode({
    client_id      = var.sap_client_id
    client_secret  = var.sap_client_secret
    token_url      = var.sap_token_url
    odata_base_url = var.sap_odata_base_url
    sap_client     = var.sap_client
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "telegram_credentials" {
  name                    = "autoreplenish/telegram-credentials-${var.environment}"
  description             = "Telegram Bot Token, pilot chat id, and webhook secret"
  recovery_window_in_days = 0

  tags = {
    Name = "Telegram Bot Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "telegram_credentials_val" {
  secret_id = aws_secretsmanager_secret.telegram_credentials.id

  secret_string = jsonencode({
    bot_token      = var.telegram_bot_token
    chat_id        = var.telegram_chat_id
    webhook_secret = var.telegram_webhook_secret
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "weather_credentials" {
  name                    = "autoreplenish/weather-credentials-${var.environment}"
  description             = "OpenWeatherMap API key and endpoint"
  recovery_window_in_days = 0

  tags = {
    Name = "OpenWeatherMap Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "weather_credentials_val" {
  secret_id = aws_secretsmanager_secret.weather_credentials.id

  secret_string = jsonencode({
    api_key      = var.openweathermap_api_key
    api_base_url = "https://api.openweathermap.org/data/2.5"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
