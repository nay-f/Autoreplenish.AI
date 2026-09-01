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
