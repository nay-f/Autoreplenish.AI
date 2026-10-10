# -------------------------------------------------------------
# DynamoDB Single Table (PRD Section 13)
# -------------------------------------------------------------
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

  # GSI1: entity-type listing and cross-store recency scans
  #   (STORE, SKU, AUDIT, FEEDBACK, SAPTRANS, CHATPENDING)
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

  # GSI2: business-key lookups
  #   AuditLog  -> AUDIT#{request_id}  (get audit trace by request id)
  #   SapTrans  -> SAPPR#{sap_pr_id}   (look up a PR document number)
  attribute {
    name = "GSI2PK"
    type = "S"
  }

  attribute {
    name = "GSI2SK"
    type = "S"
  }

  global_secondary_index {
    name            = "GSI2"
    hash_key        = "GSI2PK"
    range_key       = "GSI2SK"
    projection_type = "ALL"
  }

  # TTL drives the weather cache expiry (PRD 11.4 - 6 hour TTL).
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
    Name           = "${var.dynamodb_table_name}-${var.environment}"
    Purpose        = "Single-table store for Cache, State, Audit, and Profiles"
    AccessPatterns = "PK/SK + GSI1 (entity listing) + GSI2 (business key)"
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
