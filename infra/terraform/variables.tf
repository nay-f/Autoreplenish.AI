variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "expected_account_id" {
  type        = string
  description = "AWS account allowed for this environment."
  default     = ""

  validation {
    condition     = var.expected_account_id == "" || can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be a 12-digit AWS account ID when supplied."
  }
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "project_name" {
  type    = string
  default = "autoreplenish"
}

variable "confirm_production" {
  type    = bool
  default = false
}

variable "enable_sap_write" {
  type    = bool
  default = false
}

variable "enable_eventbridge" {
  type    = bool
  default = true
}

variable "lambda_artifact_path" {
  type    = string
  default = "../../build/lambda.zip"
}

variable "bedrock_model_id" {
  type    = string
  default = ""
}

variable "bedrock_model_arn" {
  type        = string
  description = "Exact Bedrock model or inference-profile ARN. Set this for least-privilege InvokeModel access."
  default     = ""
}

variable "secret_name" {
  type    = string
  default = ""
}

variable "alarm_sns_topic_arn" {
  type    = string
  default = ""
}

variable "allowed_origins" {
  type        = list(string)
  description = "Browser origins allowed to call the dashboard API."
  default     = ["http://localhost:5173"]

  validation {
    condition     = length(var.allowed_origins) > 0 && alltrue([for origin in var.allowed_origins : can(regex("^https?://", origin))])
    error_message = "allowed_origins must contain at least one http:// or https:// origin."
  }
}
