resource "aws_secretsmanager_secret" "application" {
  name                    = var.secret_name != "" ? var.secret_name : "${local.name_prefix}/application"
  recovery_window_in_days = local.is_prod ? 30 : 0
}

resource "aws_secretsmanager_secret" "sap" {
  name                    = "${local.name_prefix}/sap"
  recovery_window_in_days = local.is_prod ? 30 : 0
}

output "secret_name" {
  value = aws_secretsmanager_secret.application.name
}

output "sap_secret_name" {
  value = aws_secretsmanager_secret.sap.name
}
