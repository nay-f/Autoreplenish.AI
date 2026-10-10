variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment (e.g., dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "dynamodb_table_name" {
  description = "Name of the single DynamoDB table for AutoReplenish.ai"
  type        = string
  default     = "autoreplenish-main"
}

variable "bedrock_model_id" {
  description = "AWS Bedrock Claude model ID for Agentic Reasoning"
  type        = string
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}

variable "morning_schedule_cron" {
  description = "Cron expression for 05:00 WIB evaluation (22:00 UTC previous day)"
  type        = string
  default     = "cron(0 22 * * ? *)"
}

variable "afternoon_schedule_cron" {
  description = "Cron expression for 14:00 WIB evaluation (07:00 UTC)"
  type        = string
  default     = "cron(0 7 * * ? *)"
}

variable "telegram_webhook_url" {
  description = "Public HTTPS URL registered with Telegram as the webhook (leave empty to skip registration)"
  type        = string
  default     = ""
}

# -------------------------------------------------------------
# Secrets (PRD Section 24: never hardcode credentials)
# All default to empty so `terraform plan` succeeds without exposing anything.
# Provide them at apply time, e.g. with a *.tfvars file that is NOT committed:
#     terraform apply -var-file=secrets.auto.tfvars
# Once populated, secret values are managed outside Terraform (see the
# ignore_changes lifecycle in secrets.tf) so re-applies never revert them.
# -------------------------------------------------------------
variable "openweathermap_api_key" {
  description = "OpenWeatherMap API key (weather-credentials secret)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "telegram_bot_token" {
  description = "Telegram bot token issued by @BotFather"
  type        = string
  default     = ""
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "Pilot store manager chat id for card delivery"
  type        = string
  default     = ""
  sensitive   = true
}

variable "telegram_webhook_secret" {
  description = "Secret token sent in the X-Telegram-Bot-Api-Secret-Token header"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sap_client_id" {
  description = "SAP S/4HANA OAuth2 client id (leave empty to run in PERSISTENT_SANDBOX mode)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sap_client_secret" {
  description = "SAP S/4HANA OAuth2 client secret (leave empty to run in PERSISTENT_SANDBOX mode)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sap_token_url" {
  description = "SAP OAuth2 token endpoint"
  type        = string
  default     = ""
}

variable "sap_odata_base_url" {
  description = "SAP OData service root, ending in API_PURCHASEREQ_PROCESS_SRV"
  type        = string
  default     = ""
}

variable "sap_client" {
  description = "SAP client (mandt) used in the x-sap-client header"
  type        = string
  default     = "100"
}
