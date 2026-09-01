resource "aws_dynamodb_table" "main_table" {
  name             = "${var.dynamodb_table_name}-${var.environment}"
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "PK"
  range_key        = "SK"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "GSI1PK"
    type = "S"
  }

  attribute {
    name = "GSI1SK"
    type = "S"
  }

  global_secondary_index {
    name            = "GSI1"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.dynamo_key.arn
  }

  tags = {
    Name        = "${var.dynamodb_table_name}-${var.environment}"
    Purpose     = "Single-table store for Cache, State, Audit, and Profiles"
  }
}

resource "aws_kms_key" "dynamo_key" {
  description             = "KMS Key for AutoReplenish DynamoDB encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "autoreplenish-dynamo-kms-${var.environment}"
  }
}
