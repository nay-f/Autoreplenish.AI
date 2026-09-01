resource "aws_secretsmanager_secret" "sap_credentials" {
  name                    = "autoreplenish/sap-credentials-${var.environment}"
  description             = "SAP S/4HANA OData API credentials and endpoints"
  recovery_window_in_days = 0

  tags = {
    Name = "SAP S/4HANA Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "sap_credentials_val" {
  secret_id     = aws_secretsmanager_secret.sap_credentials.id
  secret_string = jsonencode({
    client_id       = "AUTOREPLENISH_CLIENT_ID"
    client_secret   = "SAP_SECURE_SECRET_TOKEN"
    token_url       = "https://sap-sandbox.example.com/oauth/token"
    odata_base_url  = "https://sap-sandbox.example.com/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV"
    sap_client      = "100"
  })
}

resource "aws_secretsmanager_secret" "telegram_credentials" {
  name                    = "autoreplenish/telegram-credentials-${var.environment}"
  description             = "Telegram Bot Token and Webhook Secret"
  recovery_window_in_days = 0

  tags = {
    Name = "Telegram Bot Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "telegram_credentials_val" {
  secret_id     = aws_secretsmanager_secret.telegram_credentials.id
  secret_string = jsonencode({
    bot_token      = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    webhook_secret = "secure_webhook_secret_hash_2026"
  })
}

resource "aws_secretsmanager_secret" "weather_credentials" {
  name                    = "autoreplenish/weather-credentials-${var.environment}"
  description             = "OpenWeatherMap API Key and endpoint"
  recovery_window_in_days = 0

  tags = {
    Name = "OpenWeatherMap Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "weather_credentials_val" {
  secret_id     = aws_secretsmanager_secret.weather_credentials.id
  secret_string = jsonencode({
    api_key      = "owm_api_key_sample_token"
    api_base_url = "https://api.openweathermap.org/data/2.5"
  })
}
