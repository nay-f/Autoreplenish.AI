# AutoReplenish.ai Deployment Runbook

This runbook describes the safe path from artifact validation to staging. It does
not authorize production deployment. Production requires a separate written
approval and explicit confirmation of the production guard variables.

## 1. Preflight

From the repository root:

```powershell
python -m compileall -q backend tests
.\venv\Scripts\python.exe -m pytest -q
aws sts get-caller-identity
```

Verify the returned account is the account in the environment matrix. Do not
continue if the identity, region, or Terraform state key is unexpected.

## 2. Build the Lambda artifact

Run the Docker/Linux build. Do not package the Windows virtual environment:

```powershell
.\scripts\build_lambda.ps1
```

Verify the ZIP contains `backend/lambda_handlers.py` at its root and does not
contain `.env`, Terraform state, or test datasets.

## 3. Validate Terraform without AWS changes

Install Terraform 1.9+ on the operator workstation or use the CI workflow.
The following commands do not access a Terraform backend or apply resources:

```powershell
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false -input=false
terraform -chdir=infra/terraform validate -no-color
```

## 4. Staging plan

Create an untracked `staging.tfvars` from the example and replace the account
ID. Never put secret values in it.

```powershell
terraform -chdir=infra/terraform init `
  -backend-config="bucket=<state-bucket>" `
  -backend-config="key=autoreplenish/staging/terraform.tfstate" `
  -backend-config="region=<region>" `
  -backend-config="dynamodb_table=<lock-table>"

terraform -chdir=infra/terraform plan `
  -var-file=staging.tfvars `
  -out=staging.tfplan

terraform -chdir=infra/terraform show staging.tfplan
```

Review that every resource name contains `staging`, SAP write is false, and no
production account/table/queue/secret is referenced. Staging `apply` requires
an explicit operator decision after this review; this agent does not run it.

## 5. Populate Secrets Manager after approved staging provisioning

Application secret:

```powershell
aws secretsmanager put-secret-value `
  --secret-id <staging-application-secret> `
  --secret-string file://staging-application-secrets.json
```

SAP secret should contain only staging OAuth/OData values and must be populated
separately. Staging remains `SAP_WRITE_ENABLED=false` unless the SAP owner has
approved the opt-in sandbox E2E test.

## 6. Staging smoke checks

1. Invoke the webhook with the wrong secret; expect `401`.
2. Invoke the webhook with the correct secret and a harmless update; expect a
   fast `200` response.
3. Run one orchestrator invocation with `environment=staging`.
4. Verify recommendation audit and Telegram delivery.
5. Approve from the authorized staging chat.
6. Verify exactly one FIFO message and `APPROVED -> ENQUEUED`.
7. Process the worker in dry-run mode and verify `SAP_DRY_RUN`.
8. Replay the same message and verify no second SAP operation.
9. Trigger the DLQ alarm using a controlled staging failure and perform the
   documented replay procedure.

## 7. Opt-in SAP staging E2E

Only after sandbox endpoint, OAuth credential, test material, plant, storage
location, and purchasing organization are confirmed:

```powershell
$env:RUN_SAP_STAGING_E2E = "true"
$env:SAP_STAGING_WRITE_ENABLED = "true"
$env:ENVIRONMENT = "staging"
.\venv\Scripts\python.exe -m pytest -q tests/test_sap_staging_e2e.py
```

This creates one test PR. Reconcile it in SAP and record the PR number before
running any replay test.

## 8. Production gate

Production is not a continuation of a staging apply. Before a production plan,
obtain explicit approval for:

- AWS account and region;
- production state key;
- production secrets;
- SAP production endpoint and OAuth client;
- pilot store/plant allowlist;
- alarm SNS topic and on-call owner;
- rollback/reconciliation readiness.

The production plan must explicitly include:

```text
confirm_production=true
enable_sap_write=true
expected_account_id=<production-account-id>
```

Never place those values in a committed example file or run apply without the
required approval.
