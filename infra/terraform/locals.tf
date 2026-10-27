locals {
  name_prefix = "${var.project_name}-${var.environment}"
  is_prod     = var.environment == "production"
  sap_write   = local.is_prod ? var.enable_sap_write : false
  table_name  = "AutoReplenish_${var.environment == "development" ? "Dev" : var.environment == "staging" ? "Staging" : "Production"}Table"
}

resource "terraform_data" "production_guard" {
  input = local.is_prod && !var.confirm_production ? "blocked" : "allowed"

  lifecycle {
    precondition {
      condition     = !local.is_prod || var.confirm_production
      error_message = "Production provisioning requires confirm_production=true."
    }

    precondition {
      condition     = !local.is_prod || var.enable_sap_write
      error_message = "Production provisioning requires explicit enable_sap_write=true."
    }

    precondition {
      condition     = !local.is_prod || var.expected_account_id != ""
      error_message = "Production provisioning requires expected_account_id."
    }
  }
}
