# AutoReplenish.ai Terraform

Terraform provisions one isolated environment per state/configuration:

- DynamoDB Single-Table with GSI1/GSI2, encryption, and PITR.
- SQS FIFO approval queue with FIFO DLQ and redrive policy.
- Separate Lambda functions and IAM roles for orchestrator, webhook, dashboard, and SAP worker.
- API Gateway HTTP API for Telegram webhook and dashboard.
- EventBridge Scheduler at 03:00 and 14:00 `Asia/Jakarta`.
- Secrets Manager placeholder; values are populated out-of-band.
- CloudWatch log groups, metric filters, and alarms.

## Artifact

Build the deployment ZIP in a Linux-compatible container before Terraform planning:

```powershell
.\scripts\build_lambda.ps1
```

The ZIP must contain `backend/` at its root and the minimal runtime dependencies
from `backend/requirements-lambda.txt`. Terraform uploads this existing ZIP
directly; it does not wrap an existing ZIP inside another archive.

## Environment isolation

Use a separate S3 backend/state key and AWS account for each environment. Always
set `expected_account_id`; the AWS provider rejects an unexpected account.

```powershell
terraform init `
  -backend-config="bucket=<terraform-state-bucket>" `
  -backend-config="key=autoreplenish/staging/terraform.tfstate" `
  -backend-config="region=us-east-1" `
  -backend-config="dynamodb_table=autoreplenish-terraform-locks"
terraform plan -var-file=staging.tfvars -out=staging.tfplan
terraform show staging.tfplan
```

Use the same backend key consistently for refresh/plan/apply. Never share a
state key between environments.

Production has three explicit gates: the expected AWS account, explicit
production confirmation, and explicit SAP write enablement:

```powershell
terraform plan -var-file=production.tfvars `
  -var="confirm_production=true" `
  -var="enable_sap_write=true" `
  -out=production.tfplan
```

Do not run `apply` until the plan, AWS account identity, and change approval are
reviewed. This repository does not run Terraform apply automatically.

## Secrets

Do not put secret values in `*.tfvars`. After provisioning, populate the secret:

```powershell
aws secretsmanager put-secret-value `
  --secret-id <environment-secret-name> `
  --secret-string file://staging-secrets.json
```

The application secret may contain `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_WEBHOOK_SECRET`, `OPENWEATHER_API_KEY`, `JWT_SECRET_KEY`,
`ADMIN_USERNAME`, and `ADMIN_PASSWORD`. Put `SAP_TOKEN_URL`, `SAP_CLIENT_ID`,
and `SAP_CLIENT_SECRET` only in the separate `<environment>/sap` secret. Only
the SAP worker role is granted access to that SAP secret.
