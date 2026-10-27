# AutoReplenish.ai Environment Matrix

This file is a template. Replace account IDs and endpoints only in the deployment
system or secret manager; do not commit real credentials.

| Boundary | Development | Staging | Production |
|---|---|---|---|
| AWS account | `<dev-account-id>` | `<staging-account-id>` | `<production-account-id>` |
| Terraform state key | `autoreplenish/development/terraform.tfstate` | `autoreplenish/staging/terraform.tfstate` | `autoreplenish/production/terraform.tfstate` |
| DynamoDB table | `AutoReplenish_DevTable` | `AutoReplenish_StagingTable` | `AutoReplenish_ProductionTable` |
| SQS queue | `autoreplenish-development-approval.fifo` | `autoreplenish-staging-approval.fifo` | `autoreplenish-production-approval.fifo` |
| Telegram bot | separate dev bot | separate staging bot | production bot |
| SAP write | `false` | `false` | explicit `true` only after pilot approval |
| SAP endpoint | none/prohibited | dedicated sandbox/test tenant | approved production tenant |
| EventBridge | off/local trigger | on, 03:00/14:00 WIB | on, 03:00/14:00 WIB |
| Secret | local env allowed | staging Secrets Manager secret | production Secrets Manager secret |

## Deployment boundary checklist

- [ ] Current AWS identity matches `expected_account_id`.
- [ ] Terraform backend bucket/key belongs to this environment.
- [ ] `DYNAMODB_TABLE`, SQS URL, secret ID, and Telegram bot all match the same environment.
- [ ] Staging and production SAP URLs are not present in development configuration.
- [ ] Production requires both `confirm_production=true` and `enable_sap_write=true`.
- [ ] No secret values are stored in Terraform variables, Git, or Lambda payloads.

## Required staging values before E2E

The opt-in test `tests/test_sap_staging_e2e.py` requires a dedicated sandbox
material and plant. Set these only in the CI secret store or local untracked
environment:

```text
RUN_SAP_STAGING_E2E=true
SAP_STAGING_WRITE_ENABLED=true
ENVIRONMENT=staging
SAP_STAGING_ODATA_URL=<sandbox OData URL>
SAP_STAGING_TOKEN_URL=<sandbox OAuth token URL>
SAP_STAGING_CLIENT_ID=<staging client ID>
SAP_STAGING_CLIENT_SECRET=<staging client secret>
SAP_STAGING_TEST_PLANT=<test plant>
SAP_STAGING_TEST_MATERIAL=<test material>
SAP_STAGING_TEST_STORAGE_LOCATION=<test storage location>
SAP_STAGING_TEST_PURCHASING_ORG=<test purchasing organization>
```

The test must be approved by the SAP owner and must be run only after verifying
that the endpoint is a sandbox/test tenant. It creates one test PR.
