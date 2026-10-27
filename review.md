# AutoReplenish.ai — Production Architecture Review & Readiness Plan

**Tanggal review:** 27 Oktober 2026  
**Status:** Production hardening implemented; AWS deployment gates remain  
**Scope:** FastAPI + DynamoDB Single-Table + Bedrock + Telegram + SAP BTP/S/4HANA  
**Environment pengujian:** Development only; tidak menggunakan resource production

---

## 1. Kesimpulan eksekutif

AutoReplenish.ai sudah memiliki fondasi bisnis yang tepat untuk production pilot:

- FastAPI sebagai Dashboard/API compatibility layer.
- DynamoDB sebagai persistent state dan audit store.
- Bedrock sebagai reasoning/recommendation layer.
- Python deterministic guardrail untuk quantity, MOQ, packaging, confidence, dan risk.
- Telegram sebagai human-in-the-loop approval channel.
- SAP BTP OAuth2 dan OData transaction boundary.

Namun, implementasi awal belum cukup untuk enterprise production karena callback Telegram
masih dapat menjalankan SAP secara sinkron, scheduler dan Telegram memakai background
thread FastAPI, serta belum ada queue/DLQ dan SAP worker yang durable.

Hardening repository sekarang mengubah target transaksi menjadi:

```text
EventBridge
    -> Orchestrator Lambda
    -> DynamoDB + signals + Bedrock + deterministic guardrail
    -> Telegram webhook
    -> DynamoDB conditional approval
    -> SQS FIFO
    -> SAP worker Lambda
    -> SAP S/4HANA OData
    -> DynamoDB status/audit
    -> Telegram result notification
```

**Verdict:** kode aplikasi sudah disiapkan untuk production pilot asynchronous, tetapi
belum boleh disebut fully production-ready sebelum AWS resources, IAM, Secrets Manager,
monitoring, dan deployment tests selesai dipasang.

---

## 2. Keputusan arsitektur

### 2.1 Bedrock tidak mengontrol quantity final

Bedrock hanya memberi reasoning dan usulan penyesuaian. Python tetap mengontrol:

- deterministic baseline;
- batas quantity;
- MOQ dan packaging multiple;
- budget dan risk policy;
- shelf-life/perishable policy;
- confidence tier;
- fallback behavior.

Output Bedrock yang invalid tidak dihitung sebagai keberhasilan AI. Audit membedakan:

```text
BEDROCK_SUCCESS
DETERMINISTIC_FALLBACK
BEDROCK_AUTHORIZATION_ERROR
BEDROCK_OUTPUT_OR_REQUEST_VALIDATION_ERROR
BEDROCK_INVALID_JSON
BEDROCK_TIMEOUT
SKIPPED_GUARDRAIL
```

Fallback selalu tampil sebagai mode berisiko dan tetap memerlukan human review.

### 2.2 Telegram hanya kanal approval

Telegram bukan system of record dan tidak boleh mengirim SAP secara langsung. Callback
approval harus melakukan:

1. verifikasi secret webhook;
2. verifikasi chat-to-store binding;
3. conditional transition `PENDING_APPROVAL -> APPROVED`;
4. publish satu message ke SQS FIFO;
5. segera mengembalikan status `ENQUEUED` kepada user.

SAP dipanggil hanya oleh worker. Retry Telegram tidak boleh menghasilkan dua PR SAP.

### 2.3 Status transaksi

State production yang direkomendasikan:

```text
PENDING_APPROVAL
    -> EDIT_REQUESTED
    -> APPROVED
    -> ENQUEUED
    -> SAP_SUBMITTING
    -> SAP_SUBMITTED

APPROVED -> QUEUE_FAILED
SAP_SUBMITTING -> SAP_FAILED
SAP_FAILED -> ENQUEUED / SAP_SUBMITTING
PENDING_APPROVAL -> REJECTED / TIMEOUT
```

`SAP_DRY_RUN` dan `BTP_VERIFIED_SANDBOX_PR` tidak dianggap sama dengan
`SAP_SUBMITTED`; dashboard harus memisahkan dry-run/sandbox verification dari
transaksi OData production.

---

## 3. Pemetaan komponen target dan repository

| Target | Implementasi | Status |
|---|---|---|
| EventBridge 03:00/14:00 WIB | `lambda_handlers.orchestrator_handler` | Adapter tersedia; rule AWS belum dipasang |
| Orchestrator Lambda | `OrchestratorService.evaluate_store` | Logic tersedia; deploy terpisah diperlukan |
| Weather/calendar/promo | `WeatherService` + orchestrator context | Tersedia; external signal perlu alarm |
| Bedrock Claude | `BedrockReasoningService` | Tersedia; inference profile/IAM harus divalidasi |
| Deterministic guardrail | Bedrock service + MOQ service | Tersedia; fallback diklasifikasi |
| Telegram webhook | `/api/v1/webhooks/telegram` + Lambda adapter | Tersedia; set webhook harus dilakukan saat deploy |
| Telegram approval | Conditional DynamoDB + `ApprovalQueueService` | Asynchronous queue flow tersedia |
| SQS FIFO | `ApprovalQueueService` | Adapter tersedia; queue dan DLQ belum diprovision |
| SAP worker Lambda | `SAPWorkerService` + `sap_worker_handler` | Handler tersedia; event source mapping belum dipasang |
| SAP OAuth2/OData | `SAPService` | Tersedia; CSRF dan metadata endpoint harus diuji di staging |
| DynamoDB Single-Table | `DynamoDBService` | Pola PK/SK tersedia; GSI/PITR perlu deployment |
| Dashboard API | FastAPI routes | Berfungsi; dapat dideploy melalui API Gateway/Lambda adapter |
| React Control Center | `dashboard/src` | Tersedia |
| Audit/metrics | DynamoDB audit + governance endpoint | Ada; CloudWatch/X-Ray/alarms perlu ditambahkan |

---

## 4. Perubahan kode yang diterapkan

### 4.1 Queue dan worker

File baru:

- `backend/src/services/approval_queue_service.py`
- `backend/src/services/sap_worker_service.py`
- `backend/lambda_handlers.py`

`ApprovalQueueService` mewajibkan URL SQS FIFO, memakai:

- `MessageGroupId = store_id` untuk ordering per toko;
- `MessageDeduplicationId = request_id` untuk deduplikasi;
- payload request, quantity, actor, dan environment.

`SAPWorkerService` melakukan conditional state transition sebelum SAP call dan
mengembalikan duplicate success untuk message retry setelah transaksi telah selesai.

### 4.2 Telegram security dan approval

- Webhook memvalidasi `X-Telegram-Bot-Api-Secret-Token` di production.
- Approval dibatasi pada Telegram chat yang terdaftar pada store.
- Approval tidak lagi melakukan SAP I/O pada proses API.
- Session registration/edit disimpan di DynamoDB, bukan hanya memory process.

### 4.3 Scheduler dan polling safety

Background Telegram polling dan scheduler FastAPI dinonaktifkan secara default melalui:

```env
ENABLE_LEGACY_BACKGROUND_WORKERS=false
```

EventBridge harus memanggil `orchestrator_handler`. Long polling hanya boleh diaktifkan
untuk local compatibility/testing, bukan pada production multi-instance API.

### 4.4 SAP safety

- CSRF fetch harus sukses dan harus mengembalikan token sebelum POST.
- `SAP_SUBMITTED` hanya untuk OData submission nyata.
- Sandbox verification dilaporkan terpisah.
- Worker menjadi satu-satunya boundary transaksi SAP.

### 4.5 Fallback observability

Audit evaluasi sekarang menyimpan:

- `is_fallback`;
- `bedrock_failure_class`;
- `evaluation_status`;
- `model_id`;
- `prompt_version`;
- `rule_engine_version`;
- latency dan warning.

Fallback tidak boleh dimasukkan ke kalibrasi confidence Bedrock.

---

## 5. Single-Table DynamoDB production design

Pola minimum yang dipertahankan:

```text
PK = STORE#<store_id>       SK = PROFILE
PK = STORE#<store_id>       SK = SKU#<sku_id>
PK = REQ#<request_id>        SK = STATE
PK = TG_SESSION#<chat_id>   SK = STATE
PK = ZONE#<zone>            SK = WEATHER#LATEST
PK = AUDIT#<store_id>       SK = TS#<timestamp>#SKU#<sku_id>
```

Untuk skala production, tambahkan event audit dan GSI:

```text
PK = REQ#<request_id>       SK = EVENT#<timestamp>#<event_id>
GSI1PK = ACTIVE_STORES      GSI1SK = STORE#<store_id>
GSI2PK = STATUS#<status>    GSI2SK = <expires_at>#REQ#<request_id>
GSI3PK = USER#<user_id>     GSI3SK = STORE#<store_id>
```

Wajib diaktifkan pada production table:

- point-in-time recovery;
- encrypted customer-managed key bila diwajibkan policy perusahaan;
- backup/restore test;
- CloudWatch consumed capacity alarms;
- pagination untuk semua Query/Scan yang masih tersisa;
- TTL hanya untuk session/cache, bukan audit legal dan state transaksi.

`list_stores()` dan global audit listing saat ini masih memiliki jalur Scan. Jalur ini
harus dipindahkan ke GSI sebelum jumlah toko besar.

---

## 6. Security production checklist

### AWS/IAM

- Gunakan Lambda execution role, bukan static AWS access key.
- Orchestrator role hanya boleh membaca resource signals, Bedrock invoke, DynamoDB read/write yang diperlukan, dan `sqs:SendMessage` bila diperlukan.
- SAP worker role hanya boleh membaca secret, menerima SQS, menulis state/audit, dan mengirim Telegram notification.
- Dashboard role tidak boleh melakukan SAP write.
- SQS redrive policy harus menunjuk ke DLQ.
- SCP dan permission boundary harus diuji pada staging account.

### Secrets

Pindahkan berikut ke AWS Secrets Manager/Parameter Store:

- Telegram bot token;
- Telegram webhook secret;
- SAP client secret;
- JWT signing key;
- OpenWeather key bila masih digunakan.

Development boleh menggunakan `.env.development`; file production/secret yang sudah ada
di workstation harus dianggap sensitif dan credential perlu dirotasi bila pernah terekspos.

### API dan identity

- JWT production secret tidak boleh memakai default.
- Role harus disertai store-level authorization.
- CORS hanya untuk domain Control Center.
- Webhook Telegram harus menggunakan secret token.
- Jangan mencatat access token, bot token, atau SAP response credential ke log.

---

## 7. SQS FIFO dan DLQ configuration

Production queue minimum:

```text
Queue: AutoReplenish-Approval.fifo
ContentBasedDeduplication: false
Deduplication: request_id
MessageGroupId: store_id
VisibilityTimeout: > maximum SAP worker duration
ReceiveCount redrive: 3–5
DLQ: AutoReplenish-Approval-DLQ.fifo
```

Alarm minimum:

- `ApproximateNumberOfMessagesVisible > 0` terlalu lama;
- DLQ message count > 0;
- worker error rate;
- SAP failure rate;
- queue age di atas SLA.

Worker Lambda harus mengembalikan `batchItemFailures` seperti pada
`backend/lambda_handlers.py`, agar hanya record gagal yang dikembalikan ke queue.

---

## 8. EventBridge dan deployment topology

Gunakan dua EventBridge Scheduler rule dengan timezone `Asia/Jakarta`:

```text
03:00 Asia/Jakarta
14:00 Asia/Jakarta
```

Keduanya memanggil Orchestrator Lambda. Jangan menjalankan scheduler di FastAPI.

Topology production:

```text
API Gateway
  -> Dashboard FastAPI/Lambda
  -> Telegram webhook Lambda

EventBridge
  -> Orchestrator Lambda

SQS FIFO
  -> SAP worker Lambda
  -> DLQ

DynamoDB Single-Table
Secrets Manager
CloudWatch Logs/Metrics/Alarms
X-Ray atau OpenTelemetry tracing
```

Infrastructure harus dikelola dengan IaC (AWS CDK, Terraform, atau CloudFormation),
termasuk environment separation:

```text
development -> AutoReplenish_DevTable, SAP_WRITE_ENABLED=false
staging     -> isolated table/queue/SAP sandbox
production  -> separate account/table/queue/secrets
```

Tidak boleh ada deploy yang hanya mengganti `.env` untuk berpindah ke production.

---

## 9. Observability dan audit

Tambahkan correlation ID yang konsisten dari evaluation sampai SAP:

```text
correlation_id = request_id
```

Metrik wajib:

- Bedrock invocation success/failure/fallback rate;
- invalid output rate;
- Bedrock latency p50/p95;
- Telegram delivery/error rate;
- approval, edit, reject, timeout rate;
- queue age dan DLQ count;
- SAP OAuth2/CSRF/OData error rate;
- SAP submitted vs sandbox verified;
- duplicate callback count;
- end-to-end approval-to-SAP latency.

Audit event harus menyimpan actor, timestamp, old status, new status, quantity, reason,
correlation ID, model/prompt version, dan SAP response reference tanpa secret.

---

## 10. Kualitas AI dan keputusan bisnis

Hasil backtest terakhir:

| Dataset | WAPE | Accuracy | Kesimpulan |
|---|---:|---:|---|
| Rossmann | 147,26% | -47,26% | Mapping/target tidak layak dipakai sebagai bukti production |
| M5 | 115,90% | -15,90% | Bedrock berjalan, tetapi forecast belum akurat |
| Favorita | 31,71% | 68,29% | Terbaik sementara, belum cukup untuk auto-order |
| Walmart | Belum ada case | - | Processor khusus masih diperlukan |

Keputusan production:

- Bedrock boleh memberi explanation dan recommendation.
- Quantity harus melewati Python guardrail.
- Human approval wajib.
- Fallback tidak boleh auto-approve.
- Tidak boleh menggunakan confidence score sebagai accuracy tanpa data actual yang sebanding.
- Tidak boleh auto-order berdasarkan hasil backtest saat ini.

Gunakan baseline pembanding, WAPE, MAE, bias, hit rate ±10/±20%, stockout, spoilage,
dan cost-sensitive loss. Target 88–94% adalah target bisnis yang harus dibuktikan pada
data operasional yang sesuai, bukan asumsi yang boleh ditampilkan sebagai hasil saat ini.

---

## 11. Test gate sebelum production

### Automated tests

- schema quantity max/MOQ/packaging;
- deterministic fallback classification;
- conditional approval race/duplicate callback;
- unauthorized Telegram chat;
- queue send failure dan `QUEUE_FAILED`;
- SQS duplicate message;
- worker retry setelah timeout;
- SAP CSRF missing/invalid;
- sandbox status tidak dihitung sebagai production submission;
- webhook secret validation;
- production config rejects default JWT secret.

### Staging tests

1. EventBridge menjalankan satu store staging.
2. Telegram webhook menerima callback dengan secret benar.
3. Chat yang tidak terdaftar ditolak.
4. Double-click hanya menghasilkan satu queue message/PR.
5. SAP timeout masuk retry lalu DLQ.
6. Worker restart dapat melanjutkan dari DynamoDB.
7. Dashboard menampilkan `ENQUEUED`, `SAP_SUBMITTING`, `SAP_SUBMITTED`, dan `SAP_FAILED` dengan benar.
8. Restore DynamoDB backup diuji.
9. Alarm CloudWatch diuji dengan failure injection.

### Go-live gate

Production pilot hanya boleh dimulai jika:

- semua P0 security/reliability test lulus;
- queue dan DLQ sudah aktif;
- SAP endpoint dan OData metadata sudah diverifikasi di staging;
- secrets tidak berasal dari static credential workstation;
- rollback dan manual reconciliation tersedia;
- satu kategori dan beberapa toko dipilih sebagai pilot;
- auto-approval tetap dinonaktifkan.

---

## 12. Runbook operasi

### SAP failure

```text
SAP_FAILED
 -> inspect CloudWatch correlation_id
 -> check OAuth2/CSRF/metadata/timeout
 -> reconcile apakah PR sudah tercipta
 -> retry hanya setelah idempotency check
```

### DLQ message

```text
DLQ > 0
 -> hentikan perluasan deployment
 -> inspect request_id dan payload
 -> cek DynamoDB state
 -> cek SAP document/reference
 -> replay setelah akar masalah diperbaiki
```

### Bedrock fallback spike

```text
fallback rate naik
 -> cek model ID/inference profile/IAM
 -> cek invalid JSON dan schema validation
 -> pertahankan deterministic fallback
 -> wajibkan manual review
 -> jangan melakukan auto-approval
```

---

## 13. Status akhir

### Sudah diperbaiki di repository

- Approval Telegram diarahkan ke conditional approval + SQS FIFO adapter.
- SAP worker service dan Lambda handler tersedia.
- `SAP_WRITE_ENABLED=false` sekarang benar-benar mencegah OAuth/OData write dan menghasilkan status `SAP_DRY_RUN`.
- Telegram webhook dan secret validation tersedia.
- Background worker legacy dinonaktifkan secara default.
- State machine memiliki status queue/processing/sandbox yang eksplisit.
- Bedrock fallback memiliki failure classification dan audit status.
- SAP CSRF token wajib valid sebelum POST.
- Store Telegram binding diterapkan untuk approval.
- Dokumentasi deployment, security, metrics, dan test gates ditambahkan.

### Masih wajib dilakukan sebelum go-live

- Provision EventBridge, API Gateway, Lambda, SQS FIFO, DLQ, DynamoDB GSI/PITR, IAM, Secrets Manager, CloudWatch, dan tracing melalui IaC.
- Pasang Lambda/API Gateway adapter yang dipilih (misalnya Mangum bila FastAPI dijalankan di Lambda).
- Uji SAP OData nyata di staging.
- Tambahkan pagination/GSI untuk query skala besar.
- Tambahkan automated tests untuk queue, webhook, worker, dan failure recovery.
- Rotasi secret yang pernah tersimpan/terekspos di workstation.

**Kesimpulan:** AutoReplenish.ai sekarang siap menjadi basis implementasi production pilot
dengan human approval, bukan auto-order. Production enterprise baru dapat dinyatakan siap
setelah deployment AWS dan staging gates pada dokumen ini selesai diverifikasi.
