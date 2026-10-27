terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  allowed_account_ids = var.expected_account_id == "" ? null : [var.expected_account_id]

  default_tags {
    tags = {
      Application = "AutoReplenish.ai"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
