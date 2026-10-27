# AutoReplenish.ai — Rollback and SAP Reconciliation Runbook

## Scope and safety

This runbook is for development, staging, and the restricted production pilot.
Do not replay, cancel, or recreate a production SAP document without the SAP
owner/procurement owner approving the action. `SAP_DRY_RUN` and
`SAP_SANDBOX_VERIFIED` are not production SAP documents.

Every investigation starts with:

- environment;
- `request_id`;
- `correlation_id`;
- store ID, SKU ID, quantity;
- DynamoDB state and audit timeline;
- SQS message ID and receive count;
- SAP PR number, if present;
- CloudWatch log stream and Lambda request ID.

Never put access tokens or secret values into tickets, logs, or chat.

## Incident severity

| Severity | Example | Immediate action |
|---|---|---|
| P0 | Unauthorized approval, duplicate SAP PR, cross-environment write | Disable production webhook/queue consumer and notify SAP owner |
| P1 | DLQ growth, SAP 5xx spike, worker errors | Pause rollout, inspect queue and replay only verified messages |
| P2 | Fallback spike, dashboard errors, delayed notifications | Keep HITL active, investigate without replaying SAP writes |

## Application rollback

1. Stop new traffic with the Lambda alias/API deployment mechanism used by the
   release pipeline. Do not destroy the database or queue.
2. Disable the EventBridge schedules for the affected environment, or set the
   orchestrator Lambda reserved concurrency to zero if evaluation must stop
   immediately.
3. Keep the SAP worker running only if the queue contains already-approved,
   verified messages and the SAP owner confirms processing may continue. For an
   unknown failure, disable the event source mapping first.
4. Deploy the last known-good Lambda artifact/version using Terraform. Verify
   the plan targets only the intended environment and AWS account.
5. Run the smoke checks:
   - webhook wrong-secret request returns `401`;
   - staging `SAP_WRITE_ENABLED=false` remains dry-run;
   - worker replay of an already-submitted request is idempotent;
   - dashboard and DynamoDB show the same state.
6. Re-enable one component at a time: webhook, worker, then scheduler.
7. Record the release version, Terraform plan, CloudWatch evidence, and
   approval in the incident ticket.

Do not use `terraform destroy` for rollback. Rollback means switching code/
Lambda version and disabling traffic; DynamoDB PITR and queues are retained.

## Queue and DLQ procedure

1. Inspect queue depth, oldest message age, DLQ depth, and receive count.
2. For every DLQ message, decode only the non-secret fields and verify:
   `request_id`, `store_id`, `sku_id`, quantity, schema version, and environment.
3. Read the DynamoDB request state:
   - `SAP_SUBMITTED`, `SAP_SANDBOX_VERIFIED`, or `SAP_DRY_RUN`: do not replay;
   - `SAP_FAILED`: reconcile SAP first, then requeue only after approval;
   - `ENQUEUED`/`SAP_SUBMITTING`: inspect worker logs and SAP status before replay;
   - unknown request or wrong environment: quarantine and escalate.
4. Replay one message at a time into the same environment FIFO queue. Preserve
   `request_id` as the message deduplication ID.
5. Watch the worker log and DynamoDB transition before replaying the next
   message. Stop if a duplicate PR or unexpected transition appears.

## SAP timeout reconciliation

A timeout after an HTTP POST is ambiguous. Never blindly retry.

1. Search SAP using the idempotency key/request ID, store, material, plant,
   quantity, and creation time. Use the SAP-supported query/API rather than a
   client-side assumption.
2. If exactly one matching PR exists, store its PR number and transition the
   request to `SAP_SUBMITTED` through the approved reconciliation procedure.
3. If no PR exists and SAP confirms the request was not accepted, requeue once
   with the same `request_id`/idempotency key.
4. If multiple matches exist, stop all retries and escalate to SAP/procurement.
5. If SAP cannot be queried, leave the request in manual review/`SAP_FAILED`
   and do not create another document.

## DynamoDB PITR recovery

1. Identify the recovery timestamp and affected environment/account.
2. Restore to a new table; never overwrite the source table immediately.
3. Compare request states, SAP references, and audit records against SAP before
   switching application configuration.
4. Run duplicate/idempotency verification against the restored table.
5. Change `DYNAMODB_TABLE` through Terraform only after owner approval.
6. Keep the original table read-only for the agreed retention period.

## Go/no-go checklist after recovery

- [ ] No unauthorized callback succeeded.
- [ ] No duplicate SAP PR was created.
- [ ] Every ambiguous timeout has a reconciliation decision.
- [ ] DLQ is empty or each remaining message has an owner/action.
- [ ] `SAP_DRY_RUN` remains distinct from `SAP_SUBMITTED`.
- [ ] CloudWatch alarms are green or acknowledged with an incident link.
- [ ] EventBridge and webhook are enabled only after the worker smoke test.
- [ ] Production re-enable has explicit owner approval.
