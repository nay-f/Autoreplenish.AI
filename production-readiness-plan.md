# AutoReplenish.ai — Production Readiness Implementation Plan

**Tanggal:** 27 Oktober 2026  
**Referensi:** `review.md`  
**Tujuan:** Mengubah fondasi aplikasi menjadi production pilot yang aman, asynchronous, idempotent, dapat diaudit, dan siap diperluas ke production enterprise.

---

## 1. Sasaran akhir

Arsitektur yang harus dicapai:

```text
EventBridge Scheduler
        |
        v
Orchestrator Lambda
        |
        +--> OpenWeather / calendar / promo / SAP signals
        +--> Deterministic baseline
        +--> Bedrock reasoning
        +--> Python guardrail
        +--> DynamoDB recommendation + audit
        +--> Telegram recommendation

Kepala Toko Approve/Edit/Reject
        |
        v
API Gateway + Telegram Webhook Lambda
        |
        +--> Verify webhook secret
        +--> Verify Telegram identity/store authorization
        +--> DynamoDB conditional state transition
        +--> SQS FIFO

SQS FIFO + DLQ
        |
        v
SAP Worker Lambda
        |
        +--> Idempotency check
        +--> OAuth2
        +--> CSRF token
        +--> SAP S/4HANA OData
        +--> DynamoDB status/audit
        +--> Telegram result notification

Dashboard API Lambda --> React Control Center
```

Syarat non-negotiable:

1. Telegram tidak boleh memanggil SAP secara sinkron.
2. Tidak ada scheduler atau polling Telegram di process FastAPI production.
3. Semua approval harus atomic dan idempotent.
4. Semua SAP write harus melalui SAP worker.
5. Fallback Bedrock harus terlihat dan tidak boleh auto-approve.
6. Development, staging, dan production memakai resource serta credential terpisah.
7. Tidak ada go-live sebelum seluruh P0 gate lulus.

---

## 2. Status awal repository

### Sudah tersedia

- FastAPI API dan React dashboard.
- DynamoDB service dengan pola PK/SK dasar.
- Orchestrator service.
- Bedrock reasoning dan deterministic fallback.
- Telegram interactive approval.
- SAP OAuth2/OData service.
- `ApprovalQueueService` dan `SAPWorkerService`.
- Lambda entry points di `backend/lambda_handlers.py`.
- Telegram webhook endpoint dan secret validation.
- Conditional state transition.
- Development safety `SAP_WRITE_ENABLED=false`.
- Target architecture dan production gates di `review.md`.

### Belum selesai

- Infrastructure as Code AWS.
- Provisioning SQS FIFO dan DLQ.
- EventBridge Scheduler.
- API Gateway/Lambda deployment adapter.
- IAM least-privilege roles.
- Secrets Manager integration.
- DynamoDB GSI, PITR, dan restore test.
- CloudWatch alarms dan tracing.
- SAP staging validation end-to-end.
- Automated queue/webhook/worker failure tests.
- Store-level Telegram authorization yang lengkap.
- Reconciliation dan retry operational workflow.

---

## 3. Environment safety boundary

### Development

```env
ENVIRONMENT=development
DYNAMODB_TABLE=AutoReplenish_DevTable
SAP_WRITE_ENABLED=false
ENABLE_LEGACY_BACKGROUND_WORKERS=false
```

- Tidak boleh menggunakan SAP production URL.
- Tidak boleh menggunakan production DynamoDB table.
- Tidak boleh mengirim PR ke SAP.
- Queue development harus terpisah atau di-mock.

### Staging

```env
ENVIRONMENT=staging
DYNAMODB_TABLE=AutoReplenish_StagingTable
SAP_WRITE_ENABLED=false
ENABLE_LEGACY_BACKGROUND_WORKERS=false
```

- Account/resource staging terpisah.
- SAP sandbox/test tenant saja.
- Telegram bot staging berbeda dari bot production.
- SQS FIFO dan DLQ staging berbeda.
- Semua failure injection dilakukan di staging.

### Production

```env
ENVIRONMENT=production
DYNAMODB_TABLE=AutoReplenish_ProductionTable
SAP_WRITE_ENABLED=true
ENABLE_LEGACY_BACKGROUND_WORKERS=false
```

- Secret berasal dari Secrets Manager/Parameter Store.
- Lambda memakai execution role, bukan static AWS access key.
- Production write dibatasi allowlist store/SAP plant selama pilot.
- Auto-approval tetap nonaktif.
- Deployment hanya melalui pipeline/IaC.

---

## 4. Urutan fase implementasi

```text
Phase 0  Baseline dan safety freeze
   ↓
Phase 1  Application contract dan state machine
   ↓
Phase 2  Queue, worker, webhook, dan Lambda packaging
   ↓
Phase 3  AWS infrastructure as code
   ↓
Phase 4  Security, secrets, dan observability
   ↓
Phase 5  Staging integration dan failure testing
   ↓
Phase 6  Production pilot terbatas
   ↓
Phase 7  Enterprise rollout
```

Jangan menjalankan fase berikutnya sebelum acceptance criteria fase sebelumnya lulus.

---

# Phase 0 — Baseline, scope, dan safety freeze

## Task

### P0.1 — Freeze environment map

- Inventaris table, queue, bot, SAP URL, Bedrock region, dan credential.
- Tandai setiap resource sebagai development, staging, atau production.
- Rotasi credential yang pernah tersimpan di file lokal atau pernah dibagikan.
- Dokumentasikan owner dan contact setiap resource.

**Output:** `environment-matrix.md` atau bagian deployment documentation.

### P0.2 — Freeze current behavior

- Simpan hasil `pytest` dan `python -m compileall -q backend`.
- Simpan Bedrock smoke test dan deterministic fallback test.
- Simpan backtest report tanpa menghitung fallback sebagai Bedrock success.
- Catat model ID, prompt version, rule engine version, dan dataset version.

### P0.3 — Safety validation

- Pastikan development/staging menggunakan `SAP_WRITE_ENABLED=false`.
- Pastikan production config menolak default JWT secret.
- Pastikan table dan queue bukan resource production saat test lokal.
- Pastikan tidak ada secret baru di Git.

## Acceptance criteria

- Semua resource memiliki environment label.
- Test development tidak dapat melakukan SAP production write.
- Baseline test dapat dijalankan ulang dengan command terdokumentasi.
- Git tidak berisi credential aktif.

---

# Phase 1 — Application contract dan state machine

## P1.1 — Finalize approval state machine

State resmi:

```text
PENDING_APPROVAL -> EDIT_REQUESTED / APPROVED / REJECTED / TIMEOUT
EDIT_REQUESTED   -> APPROVED / REJECTED / TIMEOUT
APPROVED         -> ENQUEUED / QUEUE_FAILED
ENQUEUED         -> SAP_SUBMITTING
SAP_SUBMITTING   -> SAP_SUBMITTED / SAP_DRY_RUN / SAP_SANDBOX_VERIFIED / SAP_FAILED
SAP_FAILED       -> ENQUEUED / SAP_SUBMITTING
```

Tasks:

- Hilangkan penggunaan `EDITED` sebagai status sukses SAP.
- `SAP_SUBMITTED` hanya berarti OData production berhasil.
- Pisahkan `SAP_DRY_RUN` dan `SAP_SANDBOX_VERIFIED` di dashboard.
- Simpan actor, timestamp, old status, new status, dan reason setiap transition.
- Tambahkan expiry processor untuk request yang melewati `expires_at`.

## P1.2 — Finalize SQS payload

```json
{
  "request_id": "REQ-...",
  "store_id": "STORE-...",
  "sku_id": "SKU-...",
  "quantity": 120,
  "actor": "telegram-chat-id",
  "environment": "staging",
  "correlation_id": "REQ-...",
  "schema_version": "1.0"
}
```

Tasks:

- Validasi semua field wajib.
- Validasi quantity terhadap max, MOQ, packaging, budget, dan store policy.
- Jangan memasukkan token atau secret ke payload.
- Propagasikan `correlation_id` ke log, audit, queue, dan SAP reference.

## P1.3 — Idempotency contract

Worker wajib:

1. Membaca request state.
2. Mengembalikan idempotent success jika sudah submitted.
3. Mengunci `APPROVED/ENQUEUED -> SAP_SUBMITTING` secara conditional.
4. Submit satu kali.
5. Menyimpan SAP PR number dan response reference.
6. Melakukan reconciliation bila timeout terjadi setelah POST.

## P1.4 — Audit event contract

Simpan `request_id`, `correlation_id`, actor, old/new status, quantity, reason, timestamp,
model/prompt version, dan SAP reference tanpa secret.

## Acceptance criteria

- Semua transition invalid ditolak unit test.
- Double-click approval hanya menghasilkan satu transition sukses.
- Replay SQS setelah SAP success tidak membuat PR baru.
- Dry-run dan sandbox tidak dihitung sebagai production submission.

---

# Phase 2 — Queue, worker, webhook, dan packaging

## P2.1 — Approval queue

- Wajibkan URL `.fifo`.
- Gunakan `MessageGroupId=store_id`.
- Gunakan `MessageDeduplicationId=request_id`.
- Tambahkan bounded timeout dan structured logging.
- Simpan message ID untuk audit bila diperlukan.

## P2.2 — SAP worker

Bedakan error:

- OAuth temporary failure: retryable.
- SAP 429/5xx: retryable.
- Invalid master data: non-retryable/manual review.
- CSRF missing: retry terbatas lalu failure.
- Validation 4xx: non-retryable sampai data diperbaiki.

SQS digunakan untuk retry dan DLQ; kode worker tidak boleh memiliki infinite retry loop.

## P2.3 — Telegram webhook

- Gunakan webhook, bukan `getUpdates` polling.
- Validasi secret header.
- Batasi request size.
- Tangani update tanpa message/callback dengan aman.
- Jawab callback cepat.
- Jangan menjalankan SAP atau evaluasi panjang di webhook.

## P2.4 — EventBridge orchestrator

- Dukung optional `store_id` untuk retry/single-store run.
- Tambahkan execution/correlation ID.
- Tangani partial failure per store.
- Untuk volume besar, ubah menjadi dispatcher ke queue/Step Functions.

## P2.5 — Lambda packaging

- Pilih API Gateway + Mangum atau container image.
- Pisahkan package/role dashboard API, webhook, orchestrator, dan SAP worker.
- Jangan menggabungkan SAP worker dengan dashboard API.

## Acceptance criteria

- Compile dan unit test lulus.
- Tidak ada SAP call dari Telegram callback API.
- Mock SQS worker memproses satu message sampai status final.
- Worker failure mengembalikan `batchItemFailures` yang benar.

---

# Phase 3 — AWS Infrastructure as Code

## Tooling

Pilih satu: AWS CDK, Terraform, atau CloudFormation/SAM. Jangan membuat production
resource manual tanpa representasi IaC.

## Resource wajib

### DynamoDB

- Table per environment dengan PK/SK.
- GSI active stores.
- GSI pending requests/status.
- GSI user/store authorization.
- PITR dan encryption.
- TTL hanya untuk session/cache.
- Capacity strategy dan consumed capacity alarm.

### SQS

- `AutoReplenish-Approval-{env}.fifo`.
- `AutoReplenish-Approval-DLQ-{env}.fifo`.
- Redrive policy.
- Visibility timeout lebih besar dari durasi worker.
- Encryption dan queue policy terbatas.

### Lambda

- Orchestrator.
- Telegram webhook.
- SAP worker.
- Dashboard API.
- Optional timeout/reconciliation worker.

### EventBridge

- Rule 03:00 `Asia/Jakarta`.
- Rule 14:00 `Asia/Jakarta`.
- Retry policy dan dead-letter target untuk invocation failure.

### API Gateway

- Dashboard routes.
- Telegram webhook route.
- Throttling dan access logging.
- WAF bila diwajibkan policy perusahaan.

### Secrets Manager

- Telegram token dan webhook secret.
- SAP client secret.
- JWT secret.
- OpenWeather key.

### CloudWatch

- Log groups dan retention policy.
- Operational dashboard.
- Metric filters.
- Alarms untuk queue, DLQ, worker, SAP, Bedrock, dan webhook.

## Acceptance criteria

- IaC plan tidak menunjukkan resource lintas environment.
- Development destroy tidak menyentuh staging/production.
- IAM policy lulus review.
- SQS event source mapping aktif di staging.
- EventBridge dapat memanggil orchestrator staging.

---

# Phase 4 — Security, identity, dan observability

## P4.1 — IAM least privilege

### Dashboard API role

- DynamoDB access dashboard saja.
- Tidak memiliki SAP write.
- Tidak memiliki SQS receive.

### Orchestrator role

- DynamoDB recommendation/audit.
- Bedrock InvokeModel ke model yang diizinkan.
- Signal secret/reference.
- Telegram send bila diperlukan.

### Telegram webhook role

- DynamoDB request/store read.
- Conditional state update.
- SQS SendMessage hanya ke approval queue.
- Tidak memiliki SAP credential/write.

### SAP worker role

- SQS receive/delete.
- DynamoDB state/audit update.
- Read SAP secret.
- Telegram result notification.

## P4.2 — Telegram authorization

- Map chat ID ke user identity.
- Simpan role dan allowed store IDs.
- Validasi callback actor, bukan hanya chat ID.
- Tolak dan audit approval dari chat tidak dikenal.

## P4.3 — Observability

Metrik minimum:

- Bedrock success, fallback, invalid output, dan p95 latency.
- Telegram delivery/error rate.
- Approval/edit/reject/timeout rate.
- Queue age, visible messages, dan DLQ count.
- SAP OAuth/CSRF/OData errors dan success rate.
- Duplicate callback count.
- Approval-to-SAP end-to-end latency.

## Acceptance criteria

- Tidak ada secret di log.
- Unauthorized Telegram callback ditolak.
- Alarm DLQ dapat dipicu di staging.
- Dashboard memisahkan queue, dry-run, sandbox, dan SAP submitted.
- Setiap PR dapat ditelusuri dari request ID ke log worker.

---

# Phase 5 — Staging integration dan failure testing

## Test matrix

| Test | Cara uji | Hasil wajib |
|---|---|---|
| Bedrock success | Invoke model staging | Audit `BEDROCK_SUCCESS` |
| Invalid JSON | Mock response invalid | Fallback, bukan AI success |
| Quantity > max | Mock `105000` | Guardrail, no invalid SAP payload |
| Bedrock AccessDenied | Deny IAM staging | Auth error, manual review |
| Duplicate Approve | Dua callback paralel | Satu approval dan satu queue message |
| Unauthorized chat | Callback chat lain | Ditolak dan diaudit |
| Queue unavailable | Deny SQS permission | `QUEUE_FAILED`, no SAP call |
| SQS duplicate | Replay message | No duplicate PR |
| SAP OAuth timeout | Inject timeout | Retryable state |
| CSRF missing | Remove CSRF header | Failure, no POST tanpa token |
| SAP 4xx | Invalid plant/material | Bounded failure/manual action |
| SAP 5xx | Temporary failure | Retry lalu DLQ |
| Worker restart | Terminate invocation | Durable retry |
| Telegram retry | Repeat webhook | No duplicate transaction |
| EventBridge retry | Repeat event | Evaluation lock works |
| Secret missing | Remove secret | Fail closed dan alarm |

## Staging business flow

1. Buat satu staging store dan test SKU.
2. Jalankan orchestrator dari EventBridge test event.
3. Verifikasi recommendation dan audit.
4. Verifikasi Telegram card.
5. Approve dari authorized staging chat.
6. Verifikasi `APPROVED -> ENQUEUED`.
7. Verifikasi SQS message.
8. Proses SAP sandbox/test tenant.
9. Verifikasi final status dan PR reference.
10. Verifikasi dashboard timeline.

## Acceptance criteria

- Semua P0 test matrix lulus.
- Tidak ada duplicate PR saat replay.
- Semua failure memiliki status retryable atau actionable.
- DLQ replay berhasil.
- Dashboard dan DynamoDB menunjukkan status yang sama.

---

# Phase 6 — Production pilot terbatas

## Scope

- 1–3 toko.
- Satu kategori risiko rendah terlebih dahulu.
- Satu SAP plant/purchasing organization.
- Human approval 100%.
- Tidak ada auto-approval.
- Quantity dan budget limit konservatif.
- Durasi 2–4 minggu atau jumlah transaksi minimum yang disepakati.

## Go-live checklist

- Production account/resource terpisah.
- IaC apply direview.
- Lambda version/alias aktif.
- API Gateway TLS/domain siap.
- EventBridge schedule aktif.
- SQS FIFO/DLQ aktif.
- DynamoDB PITR aktif.
- Secrets Manager aktif.
- IAM review selesai.
- Webhook secret aktif.
- Store-level authorization diuji.
- CloudWatch alarms aktif.
- On-call owner dan runbook tersedia.
- Manual SAP reconciliation tersedia.
- Rollback diuji.
- Store manager dan procurement owner dilatih.

## Pilot metrics

Pantau harian:

- recommendations;
- fallback/invalid output;
- acceptance/edit/reject/timeout;
- queue age/DLQ;
- SAP success/failure;
- stockout/overstock/spoilage;
- manual intervention;
- duplicate prevention;
- end-to-end latency.

## Stop conditions

Hentikan perluasan jika terjadi:

- duplicate PR atau idempotency failure;
- unauthorized approval berhasil;
- DLQ tidak tertangani;
- SAP failure melewati threshold bisnis;
- fallback spike tanpa root cause;
- quantity guardrail bypass;
- audit event hilang;
- environment boundary violation.

---

# Phase 7 — Enterprise rollout

## Prasyarat

- Pilot selesai tanpa P0 incident.
- Reliability target tercapai.
- SAP reconciliation terbukti.
- Forecast evaluation memakai actual operational data yang valid.
- Store-level authorization selesai.
- GSI/capacity strategy tervalidasi.

## Sequence

1. Tambah toko per region.
2. Tambah kategori non-perishable.
3. Tambah perishable dengan approval lebih ketat.
4. Tambah plant/purchasing organization.
5. Tambah approval hierarchy berdasarkan nilai dan risiko.
6. Pertimbangkan automation hanya setelah governance review.

## Automation policy

```text
Fallback atau confidence < 0.65
    -> manual review tingkat lebih tinggi

Confidence 0.65–0.84
    -> Store Manager approval wajib

Confidence >= 0.85 + policy lulus
    -> Store Manager approval tetap wajib pada fase awal

Auto-approval
    -> hanya setelah governance board menyetujui evidence operasional
```

Human-in-the-loop tetap dipertahankan untuk transaksi procurement berdampak finansial.

---

## 5. Rencana automated tests

Tambahkan test file:

```text
tests/test_approval_queue.py
tests/test_sap_worker.py
tests/test_telegram_webhook.py
tests/test_state_transitions.py
tests/test_idempotency.py
tests/test_production_config.py
tests/test_fallback_classification.py
tests/test_lambda_handlers.py
```

Minimum coverage:

- boto3 SQS mock;
- DynamoDB conditional failure;
- SAP OAuth/CSRF/OData mock;
- Telegram callback actor mock;
- parallel/double callback;
- production config fail-closed;
- dry-run tidak melakukan SAP network write.

Command wajib:

```powershell
python -m compileall -q backend
.\venv\Scripts\python.exe -m pytest -q
```

CI wajib berjalan tanpa credential production.

---

## 6. Definition of Done

### Application

- [ ] Tidak ada SAP call dari Telegram webhook/API callback.
- [ ] Approval memakai conditional write.
- [ ] Approval mengirim SQS FIFO message.
- [ ] SAP hanya dipanggil worker.
- [ ] Worker idempotent.
- [ ] Fallback Bedrock diklasifikasikan.
- [ ] Dry-run, sandbox, dan production submission terpisah.
- [ ] Audit event lengkap.

### AWS

- [ ] IaC tersedia dan direview.
- [ ] Resource environment terisolasi.
- [ ] EventBridge aktif.
- [ ] SQS FIFO + DLQ aktif.
- [ ] Lambda event source mapping aktif.
- [ ] API Gateway/webhook aktif.
- [ ] DynamoDB PITR/GSI aktif.
- [ ] IAM least privilege lulus review.
- [ ] Secrets Manager aktif.
- [ ] CloudWatch alarms aktif.

### Testing

- [ ] Unit test lulus.
- [ ] Integration test staging lulus.
- [ ] Duplicate approval test lulus.
- [ ] SAP retry/DLQ test lulus.
- [ ] Restore backup test lulus.
- [ ] Rollback test lulus.
- [ ] Security test lulus.

### Operations

- [ ] On-call owner ditentukan.
- [ ] Runbook tersedia.
- [ ] Operational dashboard tersedia.
- [ ] Manual reconciliation tersedia.
- [ ] Pilot scope disetujui business owner.
- [ ] Auto-approval tetap nonaktif.

---

## 7. Prioritas

### P0 — Blocking production

1. IaC dan environment isolation.
2. SQS FIFO + DLQ.
3. SAP worker Lambda.
4. Telegram webhook secret validation.
5. IAM least privilege.
6. Secrets Manager.
7. Idempotency dan duplicate callback tests.
8. SAP staging end-to-end test.
9. CloudWatch alarms.
10. Rollback dan reconciliation runbook.

### P1 — Sebelum pilot expansion

1. DynamoDB GSI/PITR/restore.
2. Store-level authorization lengkap.
3. Timeout/expiry processor.
4. Approval escalation.
5. Partial failure handling orchestrator.
6. X-Ray/OpenTelemetry tracing.
7. Operational dashboard.
8. Automated failure injection.

### P2 — Enterprise scale

1. Step Functions atau dispatcher untuk volume besar.
2. Multi-tenant authorization.
3. Canary deployment.
4. Cost-sensitive forecast evaluation.
5. Category-specific approval policy.
6. Controlled automation review.

---

## 8. Keputusan final

Plan ini dijalankan berurutan dan tidak boleh dilewati hanya karena human approval sudah tersedia.

Human approval Telegram adalah salah satu lapisan kontrol, bukan pengganti:

```text
conditional state transition
+ SQS FIFO
+ DLQ
+ idempotent SAP worker
+ webhook authentication
+ IAM least privilege
+ Secrets Manager
+ audit trail
+ monitoring
+ reconciliation
+ rollback
```

Target realistis adalah **production pilot asynchronous dengan human approval**, bukan auto-order penuh. Auto-order hanya dapat dipertimbangkan setelah reliability, data operasional, dan governance memenuhi seluruh gate pada `review.md` dan plan ini.
