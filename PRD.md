# PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Nama Produk:** AutoReplenish.ai  
**Versi Dokumen:** 1.0  
**Status:** Ready for AI Antigravity Execution  
**Bahasa Implementasi:** Indonesia, dengan istilah teknis Inggris bila diperlukan  
**Target Eksekusi:** AI Antigravity / AI Agent untuk pengembangan produk, arsitektur, kode, dan dokumentasi teknis

---

## 1. CONTEXT FOR AI ANTIGRAVITY

You are acting as a Senior Product Architect, Cloud Architect, AI Engineer, and Full-Stack Developer combined. Use this PRD as the single source of truth to design, generate, or refine implementation artifacts for AutoReplenish.ai.

Your outputs must follow the product direction, architecture, constraints, data model, and business logic defined below. Do not introduce new cloud platforms, frameworks, or major dependencies unless explicitly requested.

The product is an Agentic AI system for minimarket replenishment. It uses AWS Bedrock as the reasoning engine, SAP S/4HANA as the system of record, AWS serverless services as orchestration infrastructure, Telegram as the human-in-the-loop interface, and React.js as the control center dashboard.

---

## 2. EXECUTIVE SUMMARY

AutoReplenish.ai adalah agen AI semi-otonom yang membantu jaringan minimarket mengurangi risiko stockout dan overstock dengan cara menghitung rekomendasi replenishment secara kontekstual.

Sistem menggabungkan:

1. Data transaksi dan inventaris dari SAP S/4HANA.
2. Sinyal eksternal seperti cuaca, promo, hari libur, dan siklus waktu.
3. Mesin penalaran generatif AWS Bedrock, menggunakan Claude 3.5 Sonnet.
4. Human-in-the-loop melalui Telegram Bot agar Kepala Toko tetap memegang kendali.
5. Dashboard React.js untuk audit, monitoring, dan analisis regional.

Alih-alih menggunakan reorder statis seperti Min-Max atau Moving Average, AutoReplenish.ai menalar hubungan antar variabel dan menghasilkan rekomendasi kuota order yang lebih presisi, disertai penjelasan natural yang mudah dipahami oleh Kepala Toko.

---

## 3. PRODUCT VISION

Menjadikan proses replenishment minimarket dari reaktif dan manual menjadi proaktif, kontekstual, dapat diaudit, dan tetap berada dalam kendali manusia.

### Vision Statement

AutoReplenish.ai helps minimarket networks prevent lost sales from stockouts while reducing capital tied up in overstock, by using Agentic AI that understands inventory, supplier schedules, promotions, weather, and human judgment.

---

## 4. PROBLEM STATEMENT

Industri minimarket dan FMCG di Indonesia beroperasi dengan margin tipis dan perputaran SKU yang sangat tinggi. Akurasi rantai pasok dari Distribution Center ke toko cabang sangat menentukan kelangsungan bisnis.

Sistem reorder konvensional bersifat statis dan memproses data historis secara terisolasi. Hal ini menyebabkan tiga masalah utama:

### 4.1 Context Blindness

Sistem konvensional mengasumsikan pola permintaan tidak berubah oleh cuaca, promo, hari libur, atau perubahan perilaku konsumen.

### 4.2 Supplier Schedule Mismatch

Pemesanan tidak mempertimbangkan lead time supplier dan jadwal kedatangan truk distribusi secara dinamis. Akibatnya, stok dapat habis sebelum pengiriman berikutnya tiba.

### 4.3 Stockout–Overstock Paradox

Lonjakan permintaan mendadak dapat memicu stockout. Sebaliknya, order standar tanpa konteks dapat memicu overstock, penumpukan barang, dan risiko kedaluwarsa.

### 4.4 Operational Burden

Dengan ratusan cabang lintas zona demografis, Kepala Toko harus mengambil banyak keputusan reorder setiap hari secara manual, tanpa alat bantu yang mempertimbangkan sinyal eksternal secara konsisten. Kualitas keputusan bergantung pada intuisi individual dan sulit diskalakan atau diaudit secara seragam.

---

## 5. PRODUCT GOALS

### 5.1 Primary Goals

1. Mengurangi stockout sebesar 35% sampai 40%.
2. Mengurangi spoilage atau kedaluwarsa hingga 50% untuk SKU sensitif.
3. Meningkatkan efisiensi modal kerja sebesar 20% sampai 30%.
4. Meningkatkan efisiensi operasional Kepala Toko hingga lebih dari 60%.

### 5.2 Secondary Goals

1. Meningkatkan transparansi keputusan replenishment.
2. Membuat setiap keputusan agen AI dapat diaudit.
3. Menstandarkan kualitas keputusan antar cabang.
4. Menggeser peran Kepala Toko dari input administratif menjadi pengawasan strategis berbasis exception handling.

---

## 6. NON-GOALS

Untuk menjaga fokus MVP dan eksekusi produksi awal, produk ini tidak bertujuan untuk:

1. Mengganti SAP S/4HANA sebagai system of record.
2. Mengganti sistem POS yang sudah berjalan.
3. Membuat forecasting engine terpisah yang memerlukan data science pipeline berat.
4. Menghapus peran Kepala Toko dalam persetujuan replenishment.
5. Melakukan auto-order penuh tanpa persetujuan manusia pada fase awal.
6. Menangani procurement strategic sourcing, negosiasi vendor, atau kontrak supplier.

---

## 7. TARGET USERS AND PERSONAS

### 7.1 Kepala Toko

**Nama Persona:** Budi  
**Peran:** Store Manager  
**Kebutuhan:**

- Rekomendasi replenishment yang cepat dan jelas.
- Penjelasan sederhana mengapa rekomendasi diberikan.
- Kemampuan approve, ubah jumlah, atau tolak dari Telegram.
- Tidak perlu membuka aplikasi berat saat sibuk di toko.

**Pain Points:**

- Terlalu banyak SKU yang harus dicek setiap hari.
- Keputusan sering bergantung intuisi.
- Cuaca, promo, dan kondisi lapangan sulit diperhitungkan secara manual.
- Takut overstock untuk produk perishable.

### 7.2 Regional Manager / Area Manager

**Nama Persona:** Siti  
**Peran:** Regional Manager  
**Kebutuhan:**

- Visibilitas kesehatan stok multi-cabang.
- Kemampuan audit keputusan AI dan tindakan Kepala Toko.
- Monitoring integrasi SAP dan anomali sistem.
- Laporan dampak terhadap stockout, overstock, dan efisiensi.

### 7.3 IT / Integration Administrator

**Nama Persona:** Andi  
**Peran:** IT Administrator / Integration Lead  
**Kebutuhan:**

- Sistem aman dan terintegrasi dengan SAP.
- Monitoring error, retry, dan audit log.
- Manajemen secrets, IAM, dan akses API.
- Kemampuan debug prompt, payload, dan keputusan agen.

### 7.4 Supply Chain / Merchandising Team

**Peran:** Supply Chain Analyst  
**Kebutuhan:**

- Memahami pola rekomendasi agen.
- Menganalisis feedback loop dari Kepala Toko.
- Mengidentifikasi SKU yang sering direvisi.
- Menyempurnakan parameter bisnis.

---

## 8. SUCCESS METRICS

### 8.1 Business Metrics

| Metric | Target | Mechanism |
|---|---:|---|
| Penurunan stockout | 35% - 40% | Kalkulasi kebutuhan real-time hingga jadwal pengiriman berikutnya |
| Pengurangan spoilage / kedaluwarsa | 50% | Penyesuaian kuota order terhadap tren weekend dan cuaca untuk SKU perishable |
| Efisiensi modal kerja terendap | 20% - 30% | Alokasi anggaran order presisi sesuai laju konsumsi riil per SKU |
| Efisiensi operasional Kepala Toko | +60% | Eliminasi identifikasi stok manual dan input draf PR, digantikan approval 1-klik via Telegram |

### 8.2 Product Metrics

| Metric | Target | Description |
|---|---:|---|
| Recommendation latency | < 30 seconds per SKU batch | Waktu dari trigger EventBridge hingga kartu Telegram terkirim |
| Telegram approval rate | > 70% | Persentase rekomendasi yang disetujui tanpa perubahan besar |
| Human override rate | < 30% | Persentase rekomendasi yang diubah atau ditolak |
| SAP PR creation success rate | > 99% | Persentase approval yang berhasil menghasilkan Purchase Requisition |
| Agent reasoning trace completeness | 100% | Setiap keputusan memiliki input, prompt, output, dan action |
| Cache hit ratio weather API | > 80% | Efisiensi pemanggilan OpenWeatherMap |

---

## 9. SOLUTION OVERVIEW

AutoReplenish.ai adalah sistem Agentic AI semi-autonomous dengan alur utama:

1. EventBridge memicu AWS Lambda sesuai jadwal.
2. Lambda memindai SKU yang mendekati threshold atau membutuhkan evaluasi.
3. Lambda mengumpulkan konteks dari SAP, OpenWeatherMap, promo internal, dan kalender.
4. Konteks dikirim ke AWS Bedrock.
5. Claude 3.5 Sonnet menalar multi-variabel dan menghasilkan rekomendasi kuota.
6. Rekomendasi dikirim ke Telegram sebagai kartu interaktif.
7. Kepala Toko dapat Approve, Ubah Jumlah, atau Tolak.
8. Jika Approve, Lambda mengirim payload ke SAP S/4HANA untuk membuat Purchase Requisition.
9. Semua aktivitas dicatat di DynamoDB dan ditampilkan di dashboard.

---

## 10. HIGH-LEVEL SYSTEM ARCHITECTURE

### 10.1 Core Components

| Component | Technology | Responsibility |
|---|---|---|
| Scheduler / Event Bus | Amazon EventBridge | Memicu evaluasi stok berdasarkan jadwal |
| Orchestrator | AWS Lambda | Orkestrasi data, API eksternal, Bedrock, Telegram, SAP |
| Reasoning Engine | AWS Bedrock - Claude 3.5 Sonnet | Analisis kontekstual dan rekomendasi kuota |
| Cache & State Store | Amazon DynamoDB | Cache cuaca, session Telegram, audit log, feedback loop |
| Secrets Management | AWS Secrets Manager | Menyimpan kredensial SAP dan API key |
| System of Record | SAP S/4HANA MM OData API | Sumber data stok, lead time, dan pembuatan PR |
| External Weather API | OpenWeatherMap | Data cuaca dan suhu harian |
| Human Interface | Telegram Bot | Approval, edit, rejection, dan notifikasi |
| Control Center | React.js | Dashboard monitoring, audit, dan trace |

### 10.2 Architecture Flow

```mermaid
flowchart LR
  A[Amazon EventBridge] --> B[AWS Lambda Orchestrator]
  B --> C[SAP S/4HANA OData API]
  B --> D[OpenWeatherMap API]
  B --> E[Internal Promo / Calendar Data]
  C --> B
  D --> B
  E --> B
  B --> F[Amazon DynamoDB Cache & State]
  B --> G[AWS Bedrock Claude 3.5 Sonnet]
  G --> B
  B --> H[Telegram Bot]
  H --> I[Store Manager]
  I --> H
  H --> J[Telegram Webhook Lambda]
  J --> F
  J --> C
  J --> B
  K[React Dashboard] --> L[API Gateway]
  L --> F
  L --> B
# PRD — Bagian 11 sampai 20
**Produk:** AutoReplenish.ai  
**Fokus Dokumen:** Functional Requirements, Data Model, Integrasi, Edge Cases, Prompt Engineering, Security, Non-Functional Requirements, User Journeys, dan Testing  
**Sumber Konteks:** Proposal AutoReplenish.ai — Agentic AI untuk mitigasi stockout & overstock pada jaringan minimarket, menggunakan AWS Bedrock, SAP S/4HANA, Telegram Bot, dan React Dashboard

---

## 11. FUNCTIONAL REQUIREMENTS

Bagian ini mendefinisikan seluruh kebutuhan fungsional utama dari AutoReplenish.ai. Setiap functional requirement harus dapat ditelusuri ke komponen teknis: AWS Lambda, Amazon EventBridge, Amazon DynamoDB, AWS Bedrock, SAP S/4HANA, Telegram Bot, dan React Dashboard.

### 11.1 FR-01 — Scheduled Stock Evaluation

**Requirement:**  
Sistem harus dapat menjalankan evaluasi replenishment secara otomatis berdasarkan jadwal.

**Deskripsi:**  
Amazon EventBridge digunakan sebagai scheduler untuk memicu AWS Lambda. Lambda kemudian memindai SKU yang perlu dievaluasi berdasarkan threshold, kategori produk, promo, lead time, dan risiko stok.

**Aturan Jadwal Default:**

- Evaluasi pagi: `05:00 WIB`
- Evaluasi sore: `14:00 WIB`
- Jadwal dapat disesuaikan per zona, per toko, atau per kategori SKU

**Acceptance Criteria:**

- EventBridge berhasil memicu Lambda sesuai jadwal.
- Lambda dapat menentukan daftar toko dan SKU yang perlu dievaluasi.
- Sistem tidak harus memproses seluruh SKU jika tidak ada pemicu risiko.
- Jadwal dapat diubah tanpa mengubah kode inti secara besar.
- Setiap run memiliki `run_id` unik untuk keperluan audit.

---

### 11.2 FR-02 — SKU Prioritization

**Requirement:**  
Sistem harus mampu memilih SKU prioritas yang perlu diproses oleh Agentic AI.

**Kriteria SKU Prioritas:**

1. Stok fisik berada di bawah safety threshold.
2. SKU termasuk kategori perishable atau sensitif cuaca.
3. SKU sedang atau akan mengikuti promo.
4. SKU memiliki burn rate tinggi.
5. Lead time supplier mendekati batas kritis.
6. SKU pernah mengalami stockout atau overstock dalam periode tertentu.
7. SKU memiliki pola permintaan tidak stabil.
8. SKU baru atau toko baru yang membutuhkan evaluasi cold start.

**Output yang Diharapkan:**

```json
{
  "run_id": "RUN-20260616-0500",
  "store_id": "STR-001",
  "selected_skus": [
    {
      "sku_id": "SKU-10023",
      "priority_score": 88,
      "reason_codes": [
        "below_threshold",
        "perishable",
        "weather_sensitive",
        "lead_time_critical"
      ]
    }
  ]
}
```

**Acceptance Criteria:**

- Lambda menghasilkan daftar SKU prioritas.
- Setiap SKU memiliki alasan seleksi.
- Sistem dapat membatasi jumlah SKU per batch untuk kontrol biaya.
- SKU non-prioritas dapat dilewati tanpa menghentikan proses utama.

---

### 11.3 FR-03 — Context Aggregation

**Requirement:**  
Sistem harus mengumpulkan seluruh konteks yang dibutuhkan sebelum AI melakukan reasoning.

**Sumber Data:**

#### 11.3.1 SAP S/4HANA

Data yang dibaca:

- Stok fisik.
- Safety threshold.
- Histori penjualan atau burn rate.
- Lead time supplier.
- Jadwal kedatangan distribusi jika tersedia.
- MOQ dan kelipatan kemasan.
- Master data SKU.
- Status open PR jika diperlukan.

#### 11.3.2 OpenWeatherMap API

Data yang diambil:

- Cuaca saat ini.
- Suhu harian.
- Probabilitas hujan.
- Forecast 24 jam.
- Forecast 48 jam jika diperlukan.

#### 11.3.3 Kalender dan Promo Internal

Data yang digunakan:

- Weekday atau weekend.
- Hari libur nasional.
- Payday effect.
- Promo aktif.
- Promo mendatang.
- Event lokal jika tersedia.

**Struktur Context Output:**

```json
{
  "store": {
    "store_id": "STR-001",
    "store_name": "Cabang Sudirman",
    "area_type": "Perkantoran",
    "zone": "JAKARTA_PUSAT"
  },
  "sku": {
    "sku_id": "SKU-10023",
    "sku_name": "Roti Manis Cokelat 100g",
    "category": "Perishable",
    "physical_stock": 12,
    "threshold": 20,
    "average_daily_burn_rate": 25,
    "lead_time_days": 2,
    "moq": 12,
    "packaging_multiple": 12
  },
  "external_context": {
    "weather": {
      "condition": "Hujan deras",
      "temperature_c": 27,
      "rain_probability": 0.8,
      "forecast": "Hujan pada Sabtu-Minggu"
    },
    "calendar": {
      "day_type": "Weekend",
      "is_public_holiday": false,
      "is_payday": false
    },
    "promo": {
      "is_active": false,
      "promo_type": null
    }
  }
}
```

**Acceptance Criteria:**

- Lambda berhasil mengumpulkan data dari SAP, cuaca, dan kalender/promo.
- Jika satu sumber gagal, sistem menggunakan fallback yang sesuai.
- Context akhir terbentuk sebagai JSON terstruktur.
- Context dapat disimpan sebagai bagian dari audit log.

---

### 11.4 FR-04 — Weather Caching

**Requirement:**  
Sistem harus menggunakan cache untuk data cuaca agar efisien, hemat biaya, dan tidak terlalu sering memanggil API eksternal.

**Aturan Cache:**

- Cache berdasarkan zona toko atau wilayah.
- Cache berlaku selama 3 jam.
- TTL DynamoDB diset 6 jam.
- Jika OpenWeatherMap gagal, gunakan cache terakhir.
- Jika tidak ada cache, beri flag `weather_unavailable`.

**Contoh Entitas Cache:**

```json
{
  "PK": "ZONE#JAKARTA_PUSAT",
  "SK": "WEATHER#2026-06-16#09",
  "temperature_c": 29,
  "condition": "Hujan deras",
  "rain_probability": 0.85,
  "forecast_summary": "Hujan pada sore dan malam hari",
  "source": "OpenWeatherMap",
  "fetched_at": "2026-06-16T09:05:00+07:00",
  "ttl": 1781234567
}
```

**Acceptance Criteria:**

- Cache digunakan jika usia data kurang dari 3 jam.
- API OpenWeatherMap hanya dipanggil saat cache miss atau expired.
- Sistem tetap berjalan jika API cuaca gagal.
- Cache otomatis kedaluwarsa menggunakan DynamoDB TTL.

---

### 11.5 FR-05 — Agentic Reasoning Engine

**Requirement:**  
AWS Bedrock harus menghasilkan rekomendasi kuantitatif dan penjelasan natural berdasarkan konteks yang diberikan.

**Model AI:**

- `anthropic.claude-3-5-sonnet`

**Variabel Penalaran Utama:**

| Variabel | Bobot | Fungsi |
|---|---:|---|
| Stok & Histori Penjualan | 35% - 40% | Menghitung defisit stok fisik terhadap safety threshold berdasarkan burn rate harian |
| Jadwal Supplier & Lead Time | 20% - 25% | Memproyeksikan kebutuhan hingga kedatangan truk distribusi berikutnya |
| Katalog Promo Internal | 15% - 20% | Menerapkan faktor pengali kuota untuk promo aktif seperti JSM atau Buy 1 Get 1 |
| Cuaca & Suhu Harian | 10% - 15% | Mendeteksi pergeseran konsumsi produk sensitif cuaca |
| Siklus Waktu & Kalender | 5% - 10% | Mempertimbangkan weekday/weekend, libur nasional, dan payday effect |

**Required Output Format:**

```json
{
  "recommended_qty": 15,
  "normal_qty": 50,
  "adjusted_qty_before_moq": 15,
  "moq_applied": false,
  "packaging_multiple_applied": true,
  "confidence_score": 0.87,
  "risk_level": "medium",
  "reasoning_narrative": "Stok di bawah threshold, namun area perkantoran sepi saat weekend dan hujan deras menurunkan kunjungan. Kuota dipotong untuk mencegah overstock dan kedaluwarsa.",
  "key_factors": [
    "below_threshold",
    "weekend_office_area_quiet",
    "heavy_rain",
    "perishable_sku",
    "lead_time_2_days"
  ],
  "warnings": [
    "SKU perishable dengan lead time 2 hari",
    "Permintaan weekend berisiko lebih rendah dari estimasi normal"
  ]
}
```

**Acceptance Criteria:**

- Output Bedrock harus berupa JSON valid.
- Penjelasan harus dalam Bahasa Indonesia.
- Output harus mengandung `recommended_qty`, `confidence_score`, dan `reasoning_narrative`.
- Jika output tidak valid, Lambda melakukan retry maksimal 2 kali.
- Jika tetap gagal, sistem menggunakan fallback rule-based.
- Setiap prompt dan output disimpan untuk audit.

---

### 11.6 FR-06 — MOQ and Packaging Adjustment

**Requirement:**  
Hasil rekomendasi AI harus disesuaikan dengan Minimum Order Quantity dan kelipatan kemasan dari DC/vendor.

**Aturan:**

1. Jika rekomendasi AI di bawah MOQ, sistem mengevaluasi apakah MOQ tetap diperlukan.
2. Jika risiko stockout lebih tinggi daripada risiko spoilage, sistem dapat menaikkan qty ke MOQ.
3. Jika SKU perishable dan risiko spoilage tinggi, sistem dapat menandai sebagai `manual_review_required`.
4. Jika qty bukan kelipatan kemasan, sistem melakukan pembulatan sesuai kebijakan.
5. Default untuk non-perishable: round up ke kelipatan kemasan.
6. Default untuk perishable: conservative rounding, kecuali confidence tinggi.

**Contoh:**

```json
{
  "ai_recommended_qty": 15,
  "moq": 12,
  "packaging_multiple": 12,
  "final_qty": 24,
  "rounding_policy": "round_up_non_perishable",
  "note": "Qty disesuaikan ke kelipatan kemasan 12 pcs"
}
```

**Acceptance Criteria:**

- Qty final yang dikirim ke Telegram sudah mempertimbangkan MOQ.
- Qty final yang dikirim ke SAP valid secara procurement.
- Jika ada penyesuaian, metadata mencatat alasan.
- SKU perishable memiliki proteksi tambahan terhadap overstock.

---

### 11.7 FR-07 — Telegram Human-in-the-Loop

**Requirement:**  
Setiap rekomendasi harus dikirim ke Kepala Toko melalui Telegram Bot dalam bentuk kartu interaktif.

**Struktur Kartu Telegram:**

```text
📦 AUTOREPLENISH.AI — Rekomendasi Replenishment Stok

Toko: Cabang Sudirman (Area Perkantoran)
SKU: Roti Manis Cokelat 100g (Perishable)

Stok Fisik: 12 Pcs
Threshold: 20 Pcs
Lead Time: 2 Hari (tiba Minggu pagi)
Cuaca: Hujan deras (Sab–Min)

🧠 Analisis Agent (AWS Bedrock):
“Stok di bawah threshold, namun area perkantoran sepi saat weekend dan hujan deras menurunkan kunjungan — kuota dipotong 70% untuk mencegah overstock & kedaluwarsa.”

💡 Rekomendasi: 15 Pcs (1 Dus) — Normal: 50 Pcs
```

**Tombol Aksi:**

1. `✅ Approve & Kirim ke SAP`
2. `✏️ Ubah Jumlah`
3. `❌ Tolak`

**Perilaku Tombol:**

| Tombol | Aksi |
|---|---|
| Approve | Lambda mengirim payload ke SAP S/4HANA untuk membuat Purchase Requisition |
| Ubah Jumlah | Telegram meminta input jumlah baru, lalu Kepala Toko melakukan konfirmasi akhir |
| Tolak | Rekomendasi dibatalkan, Kepala Toko diminta memberi alasan, alasan disimpan sebagai feedback |

**Acceptance Criteria:**

- Kartu Telegram menampilkan konteks lengkap.
- Narasi AI mudah dipahami oleh Kepala Toko.
- Kepala Toko dapat mengambil keputusan tanpa membuka aplikasi lain.
- Setiap klik tombol dicatat di DynamoDB.
- Sistem mencegah duplikasi proses akibat klik ganda.

---

### 11.8 FR-08 — Approval State Management

**Requirement:**  
Sistem harus menyimpan status approval secara konsisten dan idempotent.

**Status yang Digunakan:**

- `PENDING_APPROVAL`
- `APPROVED`
- `EDITED`
- `REJECTED`
- `TIMEOUT`
- `FAILED_SAP`
- `PR_CREATED`

**Contoh Entitas State:**

```json
{
  "PK": "REQ#REQ-20260616-0001",
  "store_id": "STR-001",
  "sku_id": "SKU-10023",
  "recommended_qty": 15,
  "status": "PENDING_APPROVAL",
  "telegram_chat_id": "123456789",
  "telegram_message_id": "987654",
  "created_at": "2026-06-16T05:10:00+07:00",
  "expires_at": "2026-06-16T09:10:00+07:00"
}
```

**Aturan Timeout:**

- Jika tidak ada respons dalam 4 jam, status menjadi `TIMEOUT`.
- Sistem mengirim reminder sekali sebelum timeout.
- Default policy: timeout tidak menghasilkan PR otomatis.
- Timeout ditampilkan di dashboard sebagai rekomendasi yang belum ditangani.

**Acceptance Criteria:**

- Status berubah sesuai aksi user.
- Klik ganda tidak membuat PR ganda.
- Timeout tertangani oleh scheduler atau Lambda checker.
- State dapat diaudit.

---

### 11.9 FR-09 — SAP Purchase Requisition Creation

**Requirement:**  
Jika Kepala Toko menyetujui rekomendasi, sistem harus membuat Purchase Requisition di SAP S/4HANA.

**Metode Integrasi:**

- SAP S/4HANA MM OData API.
- Dapat melalui SAP Integration Suite atau endpoint resmi yang aman.
- Authentication menggunakan OAuth2 atau mekanisme resmi SAP.
- Credentials disimpan di AWS Secrets Manager.

**Contoh Payload PR:**

```json
{
  "PurchaseRequisitionType": "NB",
  "PurchaseRequisitionItems": [
    {
      "Material": "SKU-10023",
      "Plant": "1000",
      "StoreLocation": "STR-001",
      "RequestedQuantity": 15,
      "BaseUnit": "PCS",
      "DeliveryDate": "2026-06-18",
      "ShortText": "AutoReplenish.ai - Roti Manis Cokelat 100g"
    }
  ]
}
```

**Acceptance Criteria:**

- PR dibuat hanya jika status approval valid.
- SAP response disimpan dalam audit log.
- Jika SAP gagal, status menjadi `FAILED_SAP`.
- Sistem mengirim notifikasi kegagalan.
- Tidak ada PR duplikat untuk request yang sama.
- Payload sesuai dengan struktur OData SAP.

---

### 11.10 FR-10 — Rejection and Feedback Loop

**Requirement:**  
Penolakan Kepala Toko harus dicatat sebagai feedback untuk memperbaiki kualitas reasoning agen.

**Alur Rejection:**

1. Kepala Toko klik `❌ Tolak`.
2. Telegram meminta alasan penolakan.
3. Alasan disimpan ke DynamoDB.
4. Sistem tidak membuat PR.
5. Feedback digunakan pada konteks reasoning berikutnya jika relevan.

**Contoh Feedback Entity:**

```json
{
  "PK": "FEEDBACK#STR-001#SKU-10023",
  "SK": "TS#2026-06-16T05:35:00Z",
  "action": "REJECTED",
  "reason": "Stok di gudang belakang masih banyak dan belum terinput",
  "original_recommended_qty": 15,
  "store_id": "STR-001",
  "sku_id": "SKU-10023",
  "created_at": "2026-06-16T05:35:00+07:00"
}
```

**Acceptance Criteria:**

- Setiap rejection memiliki alasan.
- Feedback dapat digunakan untuk context injection berikutnya.
- Dashboard menampilkan rejection rate dan alasan paling sering.
- Sistem tidak mengulang rekomendasi yang sama tanpa mempertimbangkan feedback terbaru.

---

### 11.11 FR-11 — Manual Quantity Edit

**Requirement:**  
Kepala Toko dapat mengubah jumlah rekomendasi sebelum approval final.

**Alur Edit:**

1. Kepala Toko klik `✏️ Ubah Jumlah`.
2. Telegram meminta input jumlah baru.
3. Sistem memvalidasi input.
4. Sistem menampilkan konfirmasi qty baru.
5. Jika dikonfirmasi, sistem mengirim qty final ke SAP.

**Validasi:**

- Qty harus integer positif.
- Qty harus memperhatikan MOQ atau kelipatan kemasan.
- Jika qty tidak sesuai kelipatan, sistem memberi saran pembulatan.
- Jika qty terlalu tinggi, sistem menampilkan warning overstock.
- Jika qty terlalu rendah, sistem menampilkan warning stockout.

**Acceptance Criteria:**

- Qty hasil edit tersimpan.
- SAP PR menggunakan qty final hasil edit.
- Audit log mencatat qty asli AI dan qty final manusia.
- Edit tidak menyebabkan duplikasi PR.

---

### 11.12 FR-12 — Auditability and Reasoning Trace

**Requirement:**  
Setiap keputusan agen harus dapat diaudit dari hulu ke hilir.

**Data Audit Wajib:**

- Store ID.
- SKU ID.
- Timestamp.
- Input context.
- Prompt version.
- Output Bedrock.
- Confidence score.
- Recommended qty.
- MOQ adjustment.
- Human action.
- Human final qty.
- Rejection reason.
- SAP response.
- Error log.

**Contoh Audit Entity:**

```json
{
  "PK": "AUDIT#STR-001",
  "SK": "TS#2026-06-16T05:12:00Z#SKU-10023",
  "request_id": "REQ-20260616-0001",
  "store_id": "STR-001",
  "sku_id": "SKU-10023",
  "input_context": {},
  "prompt_version": "v1.0",
  "bedrock_output": {},
  "final_recommended_qty": 15,
  "human_action": "APPROVED",
  "human_final_qty": 15,
  "sap_pr_status": "SUCCESS",
  "sap_pr_id": "PR-4500012345",
  "created_at": "2026-06-16T05:12:00+07:00"
}
```

**Acceptance Criteria:**

- Dashboard dapat menampilkan trace lengkap.
- Auditor dapat menelusuri PR SAP kembali ke prompt AI.
- Setiap keputusan memiliki `request_id` unik.
- Audit log tidak boleh diubah sembarangan.

---

### 11.13 FR-13 — Control Center Dashboard

**Requirement:**  
Dashboard React.js harus menyediakan visibilitas regional, audit, dan monitoring integrasi.

**Modul Dashboard:**

#### 11.13.1 Multi-Store Inventory Health

Menampilkan:

- Status stok per toko.
- SKU berisiko stockout.
- SKU berisiko overstock.
- Heatmap cabang.
- Filter area, kategori, SKU, dan status.

#### 11.13.2 Agent Reasoning Trace & Audit Log

Menampilkan:

- Prompt version.
- Input context.
- Output Bedrock.
- Confidence score.
- Reasoning narrative.
- Keputusan manusia.
- Hasil SAP.

#### 11.13.3 SAP Integration Monitor

Menampilkan:

- Status koneksi SAP.
- PR creation success rate.
- Failed PR.
- Retry queue.
- Latency OData call.

#### 11.13.4 Feedback Analytics

Menampilkan:

- Approval rate.
- Rejection rate.
- Edit rate.
- Alasan rejection paling sering.
- Selisih rekomendasi AI vs keputusan manusia.
- SKU dengan override tertinggi.

**Acceptance Criteria:**

- Dashboard dapat mengambil data dari API Gateway dan DynamoDB.
- Data dapat difilter berdasarkan tanggal, toko, SKU, dan status.
- Dashboard hanya dapat diakses oleh role yang berwenang.
- Trace AI dapat ditampilkan secara lengkap.

---

## 12. AGENTIC AI DESIGN PRINCIPLES

AutoReplenish.ai harus dibangun sebagai agen AI yang praktis, dapat dijelaskan, dan tetap berada dalam pengawasan manusia. Prinsip berikut menjadi acuan desain.

### 12.1 Semi-Autonomous

AI tidak mengambil tindakan final tanpa persetujuan manusia pada fase awal.

**Implikasi:**

- Rekomendasi dikirim ke Telegram terlebih dahulu.
- Purchase Requisition hanya dibuat setelah approval.
- Kepala Toko tetap memiliki kendali penuh.

---

### 12.2 Explainable

Setiap rekomendasi harus memiliki narasi yang mudah dipahami.

**Implikasi:**

- Output Bedrock harus mengandung `reasoning_narrative`.
- Narasi menggunakan Bahasa Indonesia.
- Penjelasan menyebut faktor utama seperti cuaca, weekend, lead time, dan promo.

---

### 12.3 Context-Aware

AI tidak hanya menggunakan histori penjualan.

**Implikasi:**

- Sistem menggabungkan stok, lead time, promo, cuaca, dan kalender.
- Keputusan harus mempertimbangkan kondisi toko dan demografi area.
- Agen harus mampu menjelaskan hubungan sebab-akibat antar variabel.

---

### 12.4 Conservative for Perishable

Untuk produk perishable, sistem harus lebih berhati-hati.

**Implikasi:**

- Hindari rekomendasi berlebihan saat cuaca buruk atau weekend sepi.
- Utamakan pencegahan spoilage.
- Gunakan confidence threshold lebih ketat.
- Tampilkan warning jika risiko kedaluwarsa tinggi.

---

### 12.5 Auditable

Semua keputusan harus dapat ditelusuri.

**Implikasi:**

- Prompt, context, output, dan aksi dicatat.
- Setiap PR SAP dapat ditelusuri ke request AI.
- Dashboard menyediakan trace lengkap.

---

### 12.6 Feedback-Driven

Penolakan dan revisi manusia harus menjadi bahan pembelajaran.

**Implikasi:**

- Rejection reason disimpan.
- Edit qty dicatat.
- Feedback dapat disuntikkan ke prompt berikutnya.
- Sistem dapat menampilkan pola override per SKU atau per toko.

---

## 13. DATA MODEL

Data model menggunakan Amazon DynamoDB sebagai cache, state store, audit log, dan feedback store. Desain dapat menggunakan single-table design untuk efisiensi akses.

### 13.1 Entity Types

| Entity | Fungsi |
|---|---|
| WeatherCache | Menyimpan cache cuaca per zona |
| TelegramState | Menyimpan status approval Telegram |
| AuditLog | Menyimpan trace keputusan AI |
| FeedbackLog | Menyimpan rejection/edit feedback |
| StoreMetadata | Menyimpan profil toko |
| SKUProfile | Menyimpan profil SKU |

---

### 13.2 Key Design

| Entity | Partition Key | Sort Key |
|---|---|---|
| WeatherCache | `ZONE#{zone_id}` | `WEATHER#{date}#{hour}` |
| TelegramState | `REQ#{request_id}` | `STATE` |
| AuditLog | `AUDIT#{store_id}` | `TS#{timestamp}#SKU#{sku_id}` |
| FeedbackLog | `FEEDBACK#{store_id}#SKU#{sku_id}` | `TS#{timestamp}` |
| StoreMetadata | `STORE#{store_id}` | `PROFILE` |
| SKUProfile | `SKU#{sku_id}` | `PROFILE` |

---

### 13.3 StoreMetadata Entity

```json
{
  "PK": "STORE#STR-001",
  "SK": "PROFILE",
  "store_id": "STR-001",
  "store_name": "Cabang Sudirman",
  "area_type": "Perkantoran",
  "zone": "JAKARTA_PUSAT",
  "sap_plant": "1000",
  "storage_location": "WH-01",
  "telegram_chat_id": "123456789",
  "active": true
}
```

---

### 13.4 SKUProfile Entity

```json
{
  "PK": "SKU#SKU-10023",
  "SK": "PROFILE",
  "sku_id": "SKU-10023",
  "sku_name": "Roti Manis Cokelat 100g",
  "category": "Perishable",
  "weather_sensitive": true,
  "moq": 12,
  "packaging_multiple": 12,
  "base_unit": "PCS",
  "default_lead_time_days": 2,
  "vendor_id": "VEN-009"
}
```

---

### 13.5 WeatherCache Entity

```json
{
  "PK": "ZONE#JAKARTA_PUSAT",
  "SK": "WEATHER#2026-06-16#09",
  "temperature_c": 29,
  "condition": "Hujan deras",
  "rain_probability": 0.85,
  "forecast_summary": "Hujan pada sore dan malam hari",
  "source": "OpenWeatherMap",
  "fetched_at": "2026-06-16T09:05:00+07:00",
  "ttl": 1781234567
}
```

---

### 13.6 TelegramState Entity

```json
{
  "PK": "REQ#REQ-20260616-0001",
  "store_id": "STR-001",
  "sku_id": "SKU-10023",
  "recommended_qty": 15,
  "status": "PENDING_APPROVAL",
  "telegram_chat_id": "123456789",
  "telegram_message_id": "987654",
  "created_at": "2026-06-16T05:10:00+07:00",
  "expires_at": "2026-06-16T09:10:00+07:00"
}
```

---

### 13.7 AuditLog Entity

```json
{
  "PK": "AUDIT#STR-001",
  "SK": "TS#2026-06-16T05:12:00Z#SKU-10023",
  "request_id": "REQ-20260616-0001",
  "store_id": "STR-001",
  "sku_id": "SKU-10023",
  "input_context": {},
  "prompt_version": "v1.0",
  "bedrock_output": {},
  "final_recommended_qty": 15,
  "human_action": "APPROVED",
  "human_final_qty": 15,
  "sap_pr_status": "SUCCESS",
  "sap_pr_id": "PR-4500012345",
  "created_at": "2026-06-16T05:12:00+07:00"
}
```

---

### 13.8 FeedbackLog Entity

```json
{
  "PK": "FEEDBACK#STR-001#SKU-10023",
  "SK": "TS#2026-06-16T05:35:00Z",
  "action": "REJECTED",
  "reason": "Stok di gudang belakang masih banyak dan belum terinput",
  "original_recommended_qty": 15,
  "store_id": "STR-001",
  "sku_id": "SKU-10023",
  "created_at": "2026-06-16T05:35:00+07:00"
}
```

---

## 14. INTEGRATION SPECIFICATIONS

Bagian ini mendefinisikan spesifikasi integrasi antara AutoReplenish.ai dan sistem eksternal.

---

### 14.1 SAP S/4HANA Read

**Tujuan:**  
Mengambil data inventaris, sales history, lead time, MOQ, dan master data SKU.

**Sumber Data:**

- Material stock.
- Sales history atau custom CDS view.
- Purchasing info record.
- Supplier schedule jika tersedia.
- SKU master data.

**Authentication:**

- OAuth2 atau mekanisme resmi SAP.
- Credentials disimpan di AWS Secrets Manager.
- Tidak boleh ada secret di code atau environment variable biasa.

**Error Handling:**

- Timeout default: 5 detik.
- Retry: exponential backoff, maksimal 3 kali.
- Jika gagal persisten, masukkan event ke DLQ.
- Jika data tidak lengkap, gunakan fallback dan flag `degraded_context`.

**Acceptance Criteria:**

- Lambda dapat membaca data SAP dengan aman.
- Data yang diambil cukup untuk membentuk context AI.
- Kegagalan SAP tidak menyebabkan sistem crash.

---

### 14.2 SAP S/4HANA Write

**Tujuan:**  
Membuat Purchase Requisition setelah approval Kepala Toko.

**Endpoint:**

- `API_PURCHASEREQ_PROCESS_SRV` atau endpoint equivalent resmi SAP.

**Idempotency:**

- Gunakan `request_id` sebagai referensi unik.
- Cek status DynamoDB sebelum POST.
- Jangan kirim ulang jika status sudah `PR_CREATED`.

**Failure Handling:**

- Simpan response error SAP.
- Update status menjadi `FAILED_SAP`.
- Kirim notifikasi ke admin atau Kepala Toko.
- Masukkan ke retry queue jika error bersifat transient.

**Acceptance Criteria:**

- PR hanya dibuat setelah approval valid.
- Tidak ada PR duplikat.
- SAP response tercatat di audit log.
- Error dapat ditampilkan di dashboard.

---

### 14.3 OpenWeatherMap API

**Tujuan:**  
Mengambil data cuaca dan forecast untuk kebutuhan reasoning.

**Cache Policy:**

- Cache per zona.
- Cache valid 3 jam.
- TTL DynamoDB 6 jam.
- Fallback ke cache terakhir jika API gagal.

**Data Mapping:**

```json
{
  "temperature": "main.temp",
  "condition": "weather[0].description",
  "rain_probability": "rain.1h or forecast probability",
  "forecast_summary": "generated summary"
}
```

**Acceptance Criteria:**

- API tidak dipanggil berlebihan.
- Cuaca tetap tersedia dalam kondisi degraded.
- Cache otomatis kedaluwarsa.

---

### 14.4 Telegram Bot API

**Tujuan:**  
Menjadi interface human-in-the-loop untuk Kepala Toko.

**Methods Used:**

- `sendMessage`
- `editMessageText`
- `answerCallbackQuery`
- Webhook handler untuk callback buttons

**Callback Data Format:**

```text
APPROVE:{request_id}
EDIT:{request_id}
REJECT:{request_id}
```

**Security:**

- Validasi update Telegram.
- Jangan menyimpan bot token di frontend.
- Rate limit aksi user.
- Gunakan HTTPS.

**Acceptance Criteria:**

- Kartu Telegram terkirim dengan format jelas.
- Tombol approve/edit/reject berfungsi.
- Callback dapat ditelusuri ke `request_id`.
- Duplikasi klik tidak menyebabkan PR ganda.

---

### 14.5 Dashboard API

**Tujuan:**  
Menyediakan data untuk React Dashboard.

**Komponen:**

- Amazon API Gateway.
- AWS Lambda sebagai backend API.
- DynamoDB sebagai sumber data.

**Endpoints yang Dibutuhkan:**

```text
GET /stores
GET /stores/{storeId}/inventory-health
GET /audit-logs
GET /audit-logs/{requestId}
GET /sap-monitor
GET /feedback-analytics
```

**Acceptance Criteria:**

- Dashboard dapat membaca data secara read-only.
- Endpoint memiliki authentication/authorization.
- Query mendukung filter tanggal, toko, SKU, dan status.

---

## 15. EDGE CASES AND FALLBACKS

Bagian ini mendefinisikan penanganan kondisi abnormal agar sistem tetap aman dan dapat dipercaya.

---

### 15.1 Cold Start — SKU atau Toko Baru

**Condition:**  
Tidak ada histori penjualan yang cukup.

**Fallback:**

1. Gunakan rata-rata burn rate dari toko terdekat dalam klaster demografi yang sama.
2. Tandai sebagai `cold_start`.
3. Turunkan confidence score.
4. Tampilkan warning di Telegram dan dashboard.

**Prompt Injection Example:**

```text
This SKU or store has limited sales history. Use cluster average burn rate from similar stores. Mark the recommendation as cold_start and reduce confidence accordingly.
```

**Acceptance Criteria:**

- Sistem tetap dapat memberi rekomendasi.
- Rekomendasi tidak overconfident.
- Dashboard menampilkan status cold start.

---

### 15.2 MOQ dan Kelipatan Kemasan Conflict

**Condition:**  
Recommended qty tidak sesuai MOQ atau kelipatan dus.

**Fallback:**

- Non-perishable: round up ke kelipatan kemasan.
- Perishable: gunakan conservative rounding atau manual review.
- Jika qty di bawah MOQ tetapi risiko stockout tinggi, rekomendasikan MOQ dengan warning.

**Acceptance Criteria:**

- Qty final valid untuk SAP.
- Warning ditampilkan jika ada konflik.
- Audit log mencatat penyesuaian.

---

### 15.3 SAP API Failure

**Condition:**  
SAP tidak dapat dihubungi.

**Fallback:**

- Retry with exponential backoff.
- Jika gagal, masukkan ke DLQ.
- Jangan membuat PR.
- Notifikasi admin.
- Status menjadi `FAILED_SAP`.

**Acceptance Criteria:**

- Sistem tidak crash.
- PR tidak ganda.
- Error terlihat di dashboard.

---

### 15.4 Weather API Failure

**Condition:**  
OpenWeatherMap tidak merespons.

**Fallback:**

- Gunakan cache terakhir.
- Tandai `weather_stale` atau `weather_unavailable`.
- Kurangi bobot variabel cuaca dalam reasoning.

**Acceptance Criteria:**

- Proses reasoning tetap berjalan.
- Sistem tidak bergantung penuh pada API eksternal.
- Degradasi konteks tercatat.

---

### 15.5 Telegram Timeout

**Condition:**  
Kepala Toko tidak merespons dalam 4 jam.

**Fallback:**

- Status menjadi `TIMEOUT`.
- Tidak ada PR otomatis.
- Kirim reminder sekali sebelum timeout.
- Tampilkan di dashboard sebagai unhandled recommendation.

**Acceptance Criteria:**

- Timeout tercatat.
- Tidak ada aksi SAP tanpa approval.
- Kepala Toko mendapat reminder.

---

### 15.6 Duplicate Button Click

**Condition:**  
Kepala Toko klik approve dua kali.

**Fallback:**

- Gunakan state check di DynamoDB.
- Jika status sudah `APPROVED` atau `PR_CREATED`, tolak aksi duplikat.
- Kirim pesan bahwa request sudah diproses.

**Acceptance Criteria:**

- Tidak ada PR ganda.
- State tetap konsisten.
- User mendapat feedback.

---

### 15.7 Invalid Bedrock Output

**Condition:**  
Bedrock tidak mengembalikan JSON valid.

**Fallback:**

- Retry hingga 2 kali.
- Jika gagal, gunakan rule-based conservative fallback.
- Tandai sebagai `ai_degraded`.
- Kirim notifikasi ke admin.

**Acceptance Criteria:**

- Sistem tidak mengirim output mentah ke Telegram.
- Rekomendasi fallback tetap aman.
- Insiden tercatat di log.

---

### 15.8 Data SAP Tidak Lengkap

**Condition:**  
Sebagian context tidak tersedia, misalnya lead time kosong.

**Fallback:**

- Gunakan default value dari SKUProfile atau StoreMetadata.
- Tandai `missing_data`.
- Turunkan confidence score.
- Tampilkan warning.

**Acceptance Criteria:**

- Sistem tetap dapat memproses SKU.
- Keputusan tidak overconfident.
- Missing data tercatat.

---

## 16. PROMPT ENGINEERING SPECIFICATION

Bagian ini mendefinisikan bagaimana prompt AI harus dirancang agar output konsisten, aman, dan dapat diproses oleh sistem.

---

### 16.1 System Prompt Template

```text
You are AutoReplenish.ai, an Agentic AI assistant for minimarket replenishment.

Your job is to recommend optimal replenishment quantity for a specific SKU at a specific store. You must reason based on inventory, supplier lead time, promotions, weather, calendar effects, and store demographics.

You are not allowed to create final business documents directly. Your output is a recommendation for human approval.

Use Indonesian for the reasoning narrative. Be concise, practical, and clear.

Output must be strict valid JSON only. Do not include markdown, explanations outside JSON, or comments.

Decision principles:
1. Prevent stockout when demand until next delivery is likely to exceed available stock.
2. Prevent overstock and spoilage, especially for perishable items.
3. Consider supplier lead time and next delivery schedule.
4. Consider active promotions.
5. Consider weather and temperature effects.
6. Consider weekday, weekend, payday, and public holiday effects.
7. Respect MOQ and packaging multiple.
8. If data is missing, be conservative and lower confidence score.

Variable priority:
- Stock and sales history: 35% - 40%
- Supplier schedule and lead time: 20% - 25%
- Internal promo catalog: 15% - 20%
- Weather and temperature: 10% - 15%
- Time cycle and calendar: 5% - 10%

Return JSON using this schema:
{
  "recommended_qty": integer,
  "normal_qty": integer,
  "adjusted_qty_before_moq": integer,
  "moq_applied": boolean,
  "packaging_multiple_applied": boolean,
  "confidence_score": number between 0 and 1,
  "risk_level": "low" | "medium" | "high",
  "reasoning_narrative": string,
  "key_factors": array of strings,
  "warnings": array of strings
}
```

---

### 16.2 User Prompt Template

```text
Store Context:
{{store_context_json}}

SKU Context:
{{sku_context_json}}

External Context:
{{external_context_json}}

Based on the data above, calculate the optimal replenishment quantity. Explain the reasoning in Indonesian. Return strict JSON only.
```

---

### 16.3 Prompt Guardrails

- Do not output free text outside JSON.
- Do not invent missing data.
- If weather unavailable, reduce weather weight.
- If cold start, use cluster benchmark and lower confidence.
- If perishable SKU and weekend demand is uncertain, prefer conservative quantity.
- Do not exceed reasonable maximum order unless justified by promo or bulk event.
- Always include warnings if risk is medium or high.

---

### 16.4 Prompt Versioning

**Requirement:**  
Setiap perubahan prompt harus memiliki versi.

**Contoh:**

```json
{
  "prompt_version": "v1.0",
  "model": "anthropic.claude-3-5-sonnet",
  "temperature": 0.2,
  "max_tokens": 1024,
  "output_format": "strict_json"
}
```

**Acceptance Criteria:**

- Prompt version tercatat di audit log.
- Perubahan prompt tidak langsung overwrite tanpa tracking.
- Dashboard dapat menampilkan prompt version.

---

## 17. SECURITY REQUIREMENTS

Keamanan harus diterapkan sejak awal karena sistem terhubung ke SAP, Telegram, API eksternal, dan dashboard internal.

---

### 17.1 IAM Least Privilege

Lambda roles harus dipisahkan berdasarkan fungsi.

| Role | Allowed Actions |
|---|---|
| DataProcessorLambdaRole | DynamoDB read/write spesifik table only |
| SapIntegrationLambdaRole | SecretsManager read specific secret, outbound SAP call |
| BedrockInvokerLambdaRole | bedrock:InvokeModel specific model |
| TelegramWebhookLambdaRole | DynamoDB state update only |
| DashboardApiLambdaRole | DynamoDB read-only untuk dashboard queries |

**Acceptance Criteria:**

- Tidak ada role dengan akses berlebihan.
- Setiap Lambda menggunakan role terpisah.
- Akses dapat diaudit.

---

### 17.2 Secrets Management

Semua secret harus disimpan di AWS Secrets Manager.

**Secrets:**

- SAP client ID.
- SAP client secret.
- SAP token URL.
- SAP OData base URL.
- OpenWeatherMap API key.
- Telegram bot token.
- Internal API keys jika diperlukan.

**Rules:**

- Tidak boleh hardcode secret.
- Tidak boleh menyimpan secret di frontend.
- Tidak boleh menampilkan secret di log.

---

### 17.3 Encryption

**At Rest:**

- DynamoDB encrypted using AWS KMS.
- CloudWatch Logs encrypted.

**In Transit:**

- Semua komunikasi API menggunakan TLS 1.2+.
- Telegram webhook menggunakan HTTPS.
- SAP integration menggunakan koneksi aman.

---

### 17.4 Access Control Dashboard

Dashboard harus mendukung role-based access.

| Role | Access |
|---|---|
| Store Manager | Rekomendasi dan histori toko sendiri |
| Regional Manager | Multi-store dashboard, audit, analytics |
| Admin / IT | Integration monitor, logs, secrets status |
| Auditor | Read-only audit trace |

**Acceptance Criteria:**

- User hanya melihat data sesuai role.
- Akses audit dibatasi.
- Login/authorization tercatat.

---

### 17.5 Data Privacy

- Tidak memasukkan data PII pelanggan ke prompt AI.
- Data yang diproses terutama agregat toko, SKU, cuaca, dan promo.
- Jika ada data karyawan atau Kepala Toko, simpan seminimal mungkin.

---

## 18. NON-FUNCTIONAL REQUIREMENTS

Bagian ini mendefinisikan kebutuhan non-fungsional untuk memastikan sistem layak produksi.

---

### 18.1 Performance

| Metric | Requirement |
|---|---|
| EventBridge to Lambda start | < 5 detik |
| Context aggregation per SKU | < 3 detik rata-rata |
| Bedrock response per SKU | < 10 detik rata-rata |
| Telegram delivery after recommendation | < 5 detik |
| Dashboard initial load | < 3 detik |

---

### 18.2 Availability

- Target availability MVP: 99.5%.
- SAP downtime tidak boleh menghentikan seluruh sistem.
- Jika SAP down, sistem dapat menandai degraded mode dan menunda PR creation.

---

### 18.3 Scalability

**Pilot:**

- 3 sampai 5 toko.

**Phase 2:**

- 50 toko.

**Phase 3:**

- Ratusan toko.

**Scalability Rules:**

- Gunakan batch processing.
- Batasi concurrency Bedrock.
- Gunakan queue untuk proses write SAP.
- Pisahkan Lambda per fungsi agar mudah scale.

---

### 18.4 Cost Control

Sistem harus mengontrol biaya AI dan API eksternal.

**Strategi:**

- Cache data cuaca.
- Proses hanya SKU prioritas.
- Batasi jumlah SKU per batch.
- Monitor token usage Bedrock.
- Gunakan rule-based fallback untuk SKU bernilai rendah jika diperlukan.

---

### 18.5 Observability

Gunakan CloudWatch untuk memantau:

- Lambda errors.
- Bedrock latency.
- SAP API latency.
- Telegram delivery failures.
- DynamoDB throttling.
- DLQ message count.
- Timeout recommendation count.
- Failed PR count.

**Alerting:**

- SAP write failure rate tinggi.
- Bedrock invalid output rate tinggi.
- Telegram timeout rate tinggi.
- DLQ message bertambah.
- Lambda error spike.

---

### 18.6 Maintainability

- Kode Lambda modular.
- Prompt versioning terpisah dari kode.
- Konfigurasi jadwal dan threshold dapat diubah tanpa deploy besar.
- Infrastruktur sebaiknya menggunakan Infrastructure as Code.

---

## 19. USER JOURNEYS

User journey menggambarkan alur penggunaan sistem dari awal hingga akhir.

---

### 19.1 Happy Path — Store Manager Approves Recommendation

**Scenario:**

- Toko: Cabang Sudirman.
- SKU: Roti Manis Cokelat 100g.
- Stok fisik: 12 pcs.
- Threshold: 20 pcs.
- Lead time: 2 hari.
- Cuaca: hujan deras.
- Hari: weekend.
- Area: perkantoran.

**Flow:**

1. EventBridge memicu evaluasi jam 05:00.
2. Lambda memilih SKU karena berada di bawah threshold dan perishable.
3. Lambda mengambil data SAP, cuaca, kalender, dan promo.
4. Bedrock menghitung rekomendasi 15 pcs, bukan 50 pcs.
5. Telegram mengirim kartu rekomendasi ke Kepala Toko.
6. Kepala Toko membaca narasi dan klik `Approve`.
7. Lambda mengirim payload ke SAP.
8. SAP membuat Purchase Requisition.
9. Dashboard menampilkan status `PR_CREATED`.
10. Audit log lengkap tersimpan.

**Expected Result:**

- PR SAP berhasil dibuat.
- Kepala Toko memahami alasan rekomendasi.
- Tidak ada input manual kompleks.
- Keputusan dapat diaudit.

---

### 19.2 Edit Path — Store Manager Changes Quantity

**Scenario:**

- AI merekomendasikan 15 pcs.
- Kepala Toko mengetahui ada kebutuhan tambahan atau kondisi lapangan khusus.

**Flow:**

1. Kepala Toko klik `Ubah Jumlah`.
2. Telegram meminta jumlah baru.
3. Kepala Toko memasukkan 24 pcs.
4. Sistem validasi MOQ dan kelipatan kemasan.
5. Sistem menampilkan konfirmasi.
6. Kepala Toko menyetujui qty final.
7. Lambda membuat PR SAP dengan qty 24 pcs.
8. Audit log mencatat qty AI 15 pcs dan qty final manusia 24 pcs.

**Expected Result:**

- Qty final sesuai keputusan manusia.
- SAP PR menggunakan qty hasil edit.
- Override tercatat sebagai feedback.

---

### 19.3 Rejection Path — Store Manager Rejects Recommendation

**Scenario:**

- AI merekomendasikan 15 pcs.
- Kepala Toko menolak karena stok fisik sebenarnya berbeda atau ada kondisi khusus.

**Flow:**

1. Kepala Toko klik `Tolak`.
2. Telegram meminta alasan.
3. Kepala Toko menulis alasan.
4. Sistem membatalkan rekomendasi.
5. Sistem menyimpan feedback.
6. Tidak ada PR SAP dibuat.
7. Dashboard menampilkan rejection reason.

**Expected Result:**

- Keputusan manusia dihormati.
- Feedback tersimpan.
- Sistem tidak membuat PR tanpa approval.

---

### 19.4 Timeout Path — No Response from Store Manager

**Scenario:**

- Rekomendasi dikirim jam 05:10.
- Kepala Toko tidak merespons.

**Flow:**

1. Sistem mengirim rekomendasi.
2. Status `PENDING_APPROVAL`.
3. Reminder dikirim setelah 3 jam.
4. Jika tidak ada respons sampai 4 jam, status menjadi `TIMEOUT`.
5. Tidak ada PR dibuat.
6. Dashboard menampilkan rekomendasi belum ditangani.

**Expected Result:**

- Tidak ada aksi otomatis yang tidak disetujui.
- Kepala Toko mendapat reminder.
- Sistem tetap aman.

---

### 19.5 Degraded Context Path — Weather API Failure

**Scenario:**

- OpenWeatherMap API gagal.
- Sistem membutuhkan context cuaca.

**Flow:**

1. Lambda mencoba memanggil OpenWeatherMap.
2. API gagal atau timeout.
3. Lambda membaca cache cuaca terakhir dari DynamoDB.
4. Sistem menandai `weather_stale`.
5. Bedrock menerima konteks dengan warning.
6. Rekomendasi tetap dibuat dengan confidence lebih rendah.

**Expected Result:**

- Proses tidak terhenti.
- Rekomendasi tetap aman.
- Degradasi context tercatat.

---

## 20. TESTING REQUIREMENTS

Pengujian harus mencakup unit test, integration test, end-to-end test, dan security test.

---

### 20.1 Unit Tests

Unit test harus mencakup logika inti.

**Coverage Minimal:**

1. SKU selection logic.
2. Priority scoring.
3. MOQ rounding logic.
4. Weather cache logic.
5. Bedrock JSON validation.
6. Telegram callback state machine.
7. SAP payload builder.
8. Fallback logic untuk missing data.
9. Timeout state transition.
10. Feedback logging.

**Contoh Test Case MOQ:**

```text
Input:
- ai_recommended_qty: 15
- category: non-perishable
- packaging_multiple: 12

Expected:
- final_qty: 24
```

**Contoh Test Case Perishable Conservative Rounding:**

```text
Input:
- ai_recommended_qty: 15
- category: perishable
- packaging_multiple: 12
- risk_level: high

Expected:
- final_qty: 12 atau manual_review_required
```

---

### 20.2 Integration Tests

Integration test harus menguji hubungan antar komponen.

**Test Scenarios:**

1. EventBridge berhasil memicu Lambda.
2. Lambda membaca mock SAP atau SAP sandbox.
3. Lambda mengambil cuaca dari cache.
4. Lambda memanggil Bedrock dan menerima JSON valid.
5. Bedrock mengembalikan JSON invalid dan fallback berjalan.
6. Telegram card berhasil dikirim.
7. Approve callback membuat PR di mock SAP.
8. Edit callback mengubah qty dan membuat PR.
9. Reject callback menyimpan alasan.
10. Timeout mengubah state menjadi TIMEOUT.
11. SAP failure mengubah status menjadi FAILED_SAP.
12. Duplicate approve tidak membuat PR ganda.

---

### 20.3 End-to-End Test

**Skenario Utama:**

- Store: Cabang Sudirman.
- SKU: Roti Manis Cokelat 100g.
- Physical stock: 12.
- Threshold: 20.
- Lead time: 2 days.
- Weather: heavy rain.
- Day: weekend.
- Area: office.

**Expected Flow:**

1. SKU terpilih sebagai prioritas.
2. Context aggregation berhasil.
3. Bedrock merekomendasikan qty lebih rendah dari normal.
4. Telegram card menampilkan narasi.
5. Kepala Toko approve.
6. PR SAP dibuat.
7. Audit log lengkap.

**Expected Result:**

- Rekomendasi sesuai konteks.
- PR SAP berhasil.
- Trace lengkap tersedia.
- Kepala Toko dapat memahami alasan AI.

---

### 20.4 Security Tests

**Test Items:**

1. Tidak ada secret muncul di log.
2. Tidak ada secret di frontend.
3. IAM roles menggunakan least privilege.
4. Telegram webhook hanya menerima update valid.
5. Dashboard endpoint menolak akses tanpa authorization.
6. DynamoDB access dibatasi per role.
7. API Gateway menggunakan authentication.
8. TLS digunakan untuk semua komunikasi eksternal.

**Acceptance Criteria:**

- Tidak ditemukan secret exposure.
- Akses lintas role dapat dicegah.
- Audit log tidak dapat diubah sembarangan oleh user biasa.

---

### 20.5 Acceptance Test Checklist

Produk dianggap siap MVP jika:

- [ ] EventBridge memicu Lambda dengan benar.
- [ ] Lambda mengumpulkan context dari SAP/mock SAP, weather cache, dan kalender/promo.
- [ ] Bedrock menghasilkan JSON valid.
- [ ] Reasoning narrative dalam Bahasa Indonesia.
- [ ] MOQ dan kelipatan kemasan diterapkan.
- [ ] Telegram card tampil lengkap.
- [ ] Approve membuat PR SAP/mock SAP.
- [ ] Edit qty menghasilkan PR dengan qty final.
- [ ] Rejection menyimpan alasan.
- [ ] Timeout tertangani.
- [ ] Audit log lengkap.
- [ ] Dashboard menampilkan trace dan monitoring.
- [ ] Tidak ada secret exposure.
- [ ] Error handling SAP, Bedrock, dan weather berjalan.

---

# PRD — Bagian 21 sampai 30
**Produk:** AutoReplenish.ai  
**Fokus Dokumen:** Implementation Phases, Rollout Strategy, Risk Mitigation, Acceptance Criteria, AI Antigravity Execution Instructions, Definition of Terms, Appendix, Final Product Principle, dan End of PRD  
**Sumber Konteks:** Proposal AutoReplenish.ai — Agentic AI untuk mitigasi stockout & overstock pada jaringan minimarket, menggunakan AWS Bedrock, SAP S/4HANA, Telegram Bot, dan React Dashboard

---

## 21. IMPLEMENTATION PHASES

Bagian ini mendefinisikan tahapan implementasi AutoReplenish.ai dari kondisi MVP hackathon menuju sistem yang siap produksi dan siap pilot di jaringan minimarket.

Proposal telah menyatakan bahwa empat fase pengembangan hackathon telah dituntaskan, yaitu:

1. Infrastruktur dan SAP mocking.
2. Konfigurasi mesin penalaran AWS Bedrock dan integrasi OpenWeatherMap.
3. Telegram Bot dan React Dashboard.
4. Pengujian integrasi end-to-end.

Dengan status tersebut, tahap berikutnya bukan membangun konsep dari nol, tetapi meningkatkan MVP menjadi sistem production-ready, teraudit, aman, dan dapat diuji di lingkungan bisnis nyata.

---

### 21.1 Phase 1 — Production Foundation

**Objective:**  
Memindahkan MVP dari pola hackathon/mock ke fondasi produksi yang aman, terintegrasi, dan dapat dipantau.

**Deliverables:**

1. Integrasi SAP S/4HANA sandbox atau production-like environment.
2. Penggantian mock SAP OData API dengan pola integrasi resmi.
3. Implementasi AWS Secrets Manager untuk kredensial SAP, OpenWeatherMap, dan Telegram.
4. IAM role terpisah dengan prinsip least privilege.
5. Skema DynamoDB production-ready untuk cache, state, audit, dan feedback.
6. Implementasi TTL untuk cache cuaca.
7. CloudWatch logging, metrics, dan alert dasar.
8. Dead Letter Queue untuk kegagalan proses.
9. Struktur Infrastruktur as Code, misalnya Terraform atau CloudFormation.

**Definition of Done:**

- Lambda dapat membaca data SAP atau mock production-like dengan pola yang aman.
- Tidak ada secret yang disimpan di kode atau environment variable biasa.
- Weather cache berfungsi dan TTL aktif.
- Audit table dan state table tersedia.
- Monitoring dasar dan log CloudWatch berjalan.
- Error SAP, cuaca, atau Bedrock tidak menghentikan seluruh proses tanpa jejak.

**Priority:**

- Keamanan.
- Integrasi data.
- Observability.
- Idempotency.

---

### 21.2 Phase 2 — Agentic Reasoning Hardening

**Objective:**  
Menjadikan mesin penalaran AWS Bedrock lebih stabil, explainable, dan aman untuk keputusan bisnis.

**Deliverables:**

1. Prompt versioning.
2. Strict JSON schema enforcement untuk output Bedrock.
3. Retry logic untuk output Bedrock yang tidak valid.
4. Confidence scoring.
5. Risk level classification.
6. Penanganan cold start untuk SKU atau toko baru.
7. Penyesuaian MOQ dan kelipatan kemasan.
8. Feedback injection dari rejection/edit history.
9. Rule-based fallback jika Bedrock gagal.
10. Prompt guardrails untuk mencegah output bebas atau tidak terstruktur.

**Definition of Done:**

- Bedrock mengembalikan JSON valid pada seluruh skenario uji utama.
- Output tidak valid dapat ditangani tanpa membuat PR salah.
- Reasoning narrative tampil dalam Bahasa Indonesia.
- MOQ dan packaging multiple diterapkan dengan benar.
- Kasus cold start menghasilkan rekomendasi yang konservatif.
- Feedback Kepala Toko dapat disimpan dan digunakan kembali sebagai konteks.

**Priority:**

- Kualitas rekomendasi.
- Keamanan keputusan.
- Explainability.
- Auditability.

---

### 21.3 Phase 3 — Human-in-the-Loop Optimization

**Objective:**  
Memastikan alur Telegram stabil, mudah digunakan, dan aman untuk Kepala Toko.

**Deliverables:**

1. Kartu rekomendasi interaktif Telegram.
2. Flow Approve, Ubah Jumlah, dan Tolak.
3. Reminder sebelum timeout.
4. State machine di DynamoDB.
5. Duplicate click prevention.
6. Timeout handling.
7. Notifikasi kegagalan SAP.
8. Notifikasi jika rekomendasi berubah status.
9. Validasi input qty manual.
10. Audit trail untuk setiap aksi Telegram.

**Definition of Done:**

- Kepala Toko dapat approve dari Telegram.
- Edit qty dapat diproses dan menghasilkan PR dengan qty final.
- Rejection menyimpan alasan.
- Timeout tidak menghasilkan PR otomatis.
- Klik ganda tidak membuat PR duplikat.
- Semua aksi Telegram tercatat di DynamoDB.

**Priority:**

- Usability.
- Governance.
- Idempotency.
- Trust.

---

### 21.4 Phase 4 — Dashboard and Auditability

**Objective:**  
Menyediakan visibilitas regional, audit trace, dan monitoring integrasi untuk Regional Manager, Supply Chain, dan IT.

**Deliverables:**

1. React.js Control Center Dashboard.
2. API Gateway endpoints untuk query dashboard.
3. Lambda read-only untuk dashboard API.
4. Halaman Multi-Store Inventory Health.
5. Halaman Agent Reasoning Trace & Audit Log.
6. Halaman SAP Integration Monitor.
7. Halaman Feedback Analytics.
8. Filter berdasarkan toko, tanggal, SKU, status, dan risk level.
9. Role-based access control untuk dashboard.
10. Export atau tampilan log untuk audit.

**Definition of Done:**

- Dashboard dapat menampilkan audit log lengkap.
- Regional Manager dapat memfilter data per toko dan tanggal.
- SAP monitor menampilkan success/failure PR creation.
- Reasoning trace dapat ditelusuri dari PR SAP hingga prompt AI.
- Feedback analytics menampilkan approval rate, rejection rate, dan edit rate.

**Priority:**

- Transparency.
- Auditability.
- Monitoring.
- Continuous improvement.

---

### 21.5 Phase 5 — Pilot / Proof of Concept

**Objective:**  
Menguji AutoReplenish.ai pada lingkungan minimarket nyata atau semi-nyata sebelum rollout lebih luas.

**Pilot Design:**

- Jumlah toko awal: 3 sampai 5 toko.
- Demografi toko sebaiknya berbeda:
  - Area perkantoran.
  - Area perumahan.
  - Area kampus/sekolah.
  - Area dengan pola cuaca atau traffic khusus jika relevan.
- SKU pilot difokuskan pada:
  - SKU perishable.
  - SKU fast moving.
  - SKU sensitif cuaca.
  - SKU yang sering promo.

**Pilot Modes:**

1. **Shadow Mode**
   - AI menghasilkan rekomendasi.
   - Tidak ada PR SAP otomatis.
   - Kepala Toko membandingkan rekomendasi AI dengan keputusan manual.
   - Tujuan: membangun trust dan mengukur akurasi.

2. **Co-Pilot Mode**
   - Rekomendasi AI menjadi draft PR.
   - Kepala Toko menyetujui melalui Telegram.
   - Setelah approve, PR dibuat di SAP.
   - Tujuan: penggunaan produksi dengan human control.

3. **Limited Automation**
   - SKU tertentu yang low-risk dapat diproses otomatis.
   - Harus ada batasan ketat:
     - Max qty.
     - Max value.
     - Non-perishable only.
     - Confidence score tinggi.
     - Tidak ada conflict flag.
   - Tujuan: menguji efisiensi otomatisasi terbatas.

**Definition of Done:**

- Pilot berjalan minimal 2 minggu.
- Data approval, rejection, edit, dan timeout terkumpul.
- Dampak terhadap stockout dan overstock dapat diestimasi.
- Feedback Kepala Toko terkumpul.
- Tidak ada insiden PR duplikat atau PR tanpa approval.
- Laporan pilot siap untuk keputusan rollout.

---

## 22. ROLLOUT STRATEGY

Rollout harus dilakukan bertahap untuk menjaga kepercayaan user, mengurangi risiko operasional, dan memastikan governance tetap kuat.

---

### 22.1 Stage 1 — Shadow Mode

**Description:**  
Sistem menghasilkan rekomendasi, tetapi tidak mengeksekusi dokumen SAP secara otomatis.

**Behavior:**

- EventBridge tetap memicu evaluasi.
- Bedrock tetap menghasilkan rekomendasi.
- Telegram tetap mengirim kartu.
- Approve tidak langsung membuat PR, atau hanya menandai sebagai “simulation approved”.
- Dashboard mencatat perbandingan antara rekomendasi AI dan keputusan aktual Kepala Toko.

**Purpose:**

- Mengukur akurasi rekomendasi.
- Mengurangi resistensi user.
- Mengumpulkan feedback tanpa risiko bisnis langsung.
- Memvalidasi kualitas reasoning narrative.

**Exit Criteria:**

- Approval simulation rate mencapai target awal, misalnya >60%.
- Tidak ada kegagalan kritis pada pipeline data.
- Reasoning narrative dapat dipahami oleh Kepala Toko.
- Edge case utama tertangani.

---

### 22.2 Stage 2 — Co-Pilot Mode

**Description:**  
Rekomendasi AI memerlukan approval manusia sebelum PR SAP dibuat.

**Behavior:**

- Kepala Toko menerima rekomendasi di Telegram.
- Approve memicu pembuatan PR SAP.
- Edit qty menghasilkan PR dengan qty final hasil revisi.
- Reject membatalkan PR dan menyimpan alasan.

**Purpose:**

- Menggunakan sistem dalam operasional nyata.
- Menjaga kendali manusia.
- Mengumpulkan data feedback loop.
- Mengukur efisiensi waktu Kepala Toko.

**Exit Criteria:**

- PR creation success rate >99%.
- Duplicate PR dapat dicegah.
- Approval rate stabil.
- Rejection reason dapat dianalisis.
- Kepala Toko merasa alur kerja lebih cepat daripada proses manual.

---

### 22.3 Stage 3 — Limited Automation

**Description:**  
Sebagian SKU low-risk dapat diproses otomatis dengan policy ketat.

**Automation Criteria:**

- SKU non-perishable.
- Confidence score tinggi, misalnya >= 0.85.
- Tidak ada warning critical.
- Qty final berada dalam batas maksimum yang diizinkan.
- Nilai order berada dalam batas maksimum yang diizinkan.
- Tidak ada rejection berulang dalam periode tertentu.
- Toko memiliki approval history yang baik.

**Purpose:**

- Mengurangi beban approval untuk keputusan repetitif berisiko rendah.
- Meningkatkan efisiensi operasional.
- Mempersiapkan otomatisasi bertahap.

**Exit Criteria:**

- Tidak ada PR otomatis yang menyebabkan overstock signifikan.
- Auto-approved SKU memiliki exception rate rendah.
- Audit trail tetap lengkap.
- Policy automation dapat di-rollback dengan cepat.

---

### 22.4 Stage 4 — Full Autonomous Mode

**Description:**  
Otomatisasi penuh untuk SKU dan toko tertentu tanpa approval per transaksi.

**Status:**  
Tidak termasuk dalam scope awal. Tahap ini hanya dapat dipertimbangkan setelah:

- Co-pilot mode stabil.
- Limited automation terbukti aman.
- Feedback loop matang.
- Governance dan audit log kuat.
- Regional Manager dan Supply Chain menyetujui policy automation.

**Purpose:**

- Efisiensi maksimal untuk keputusan rutin.
- Kepala Toko fokus pada exception handling.
- Sistem menjadi semakin proaktif.

**Governance Requirement:**

- Auto-order harus memiliki batas nilai dan quantity.
- Harus ada kill switch.
- Semua keputusan tetap tercatat.
- Harus ada review berkala.
- Harus ada mekanisme rollback cepat.

---

### 22.5 Rollout Governance

Setiap tahap rollout harus memiliki:

1. **Scope toko dan SKU yang jelas.**
2. **KPI yang diukur.**
3. **Penanggung jawab operasional.**
4. **Mekanisme escalation.**
5. **Kill switch untuk menghentikan auto-order.**
6. **Review harian atau mingguan selama pilot.**
7. **Laporan hasil sebelum naik tahap.**

---

## 23. RISKS AND MITIGATIONS

Bagian ini mendaftar risiko utama dan mitigasi yang harus diterapkan.

---

### 23.1 Risk Matrix

| Risk | Impact | Mitigation |
|---|---|---|
| AI hallucination atau reasoning salah | Overstock, stockout, spoilage | Strict JSON output, guardrails, confidence score, human approval, audit trace |
| Bedrock output tidak valid | Proses gagal atau rekomendasi tidak dapat diproses | Retry, fallback rule-based, flag `ai_degraded`, alerting |
| SAP API tidak stabil | PR gagal dibuat, data context tidak lengkap | Retry, timeout, DLQ, degraded mode, SAP monitor |
| Weather API gagal | Context cuaca hilang | Cache DynamoDB, stale fallback, kurangi bobot cuaca |
| Store manager mengabaikan Telegram | Rekomendasi tidak tertangani | Reminder, timeout policy, dashboard alert |
| Duplicate PR | Procurement error | Idempotency key, state machine, duplicate click prevention |
| Data quality buruk | Rekomendasi tidak akurat | Validasi data, fallback, cold start logic, human review |
| MOQ/packaging conflict | Qty tidak valid untuk SAP | MOQ adjustment, packaging multiple logic, warning |
| User distrust | Adopsi rendah | Explainable narrative, edit/reject option, shadow mode |
| Cost Bedrock/API tinggi | Biaya operasional meningkat | Caching, batch limit, priority SKU, token monitoring |
| Security breach | Kebocoran kredensial atau data | Secrets Manager, IAM least privilege, TLS, RBAC |
| Regulatory/compliance issue | Audit gagal, governance lemah | Audit log lengkap, role-based access, traceability |

---

### 23.2 Critical Risk Handling

#### 23.2.1 Wrong Recommendation Leading to Overstock

**Mitigation:**

- Konservatif untuk SKU perishable.
- Tampilkan warning jika confidence rendah.
- Gunakan feedback rejection.
- Batasi auto-order untuk SKU sensitif.
- Kepala Toko selalu memiliki opsi Tolak atau Ubah Jumlah.

#### 23.2.2 Wrong Recommendation Leading to Stockout

**Mitigation:**

- Proyeksikan kebutuhan sampai jadwal pengiriman berikutnya.
- Pertimbangkan lead time supplier.
- Gunakan safety threshold.
- Tampilkan warning jika risiko stockout tinggi.
- Untuk SKU critical, utamakan pencegahan stockout.

#### 23.2.3 SAP PR Duplication

**Mitigation:**

- Gunakan `request_id` unik.
- Cek state DynamoDB sebelum POST ke SAP.
- Tolak callback jika status sudah `APPROVED` atau `PR_CREATED`.
- Tampilkan pesan bahwa request sudah diproses.

#### 23.2.4 Prompt Injection or Unexpected AI Output

**Mitigation:**

- Prompt hanya menerima context terstruktur dari sistem.
- User input bebas tidak langsung dimasukkan ke prompt tanpa sanitasi.
- Output harus valid JSON.
- Reject output yang mengandung instruksi tidak relevan.
- Simpan prompt dan output untuk audit.

---

## 24. ACCEPTANCE CRITERIA SUMMARY

Produk dianggap siap MVP production/pilot jika seluruh kriteria berikut terpenuhi.

---

### 24.1 Core Pipeline Acceptance

- [ ] Amazon EventBridge berhasil memicu AWS Lambda sesuai jadwal.
- [ ] Lambda dapat memilih SKU prioritas berdasarkan threshold, kategori, promo, lead time, dan risiko.
- [ ] Lambda berhasil mengumpulkan context dari SAP/mock SAP, weather cache, dan kalender/promo.
- [ ] Weather caching bekerja dengan DynamoDB TTL.
- [ ] Sistem tetap berjalan jika OpenWeatherMap gagal.
- [ ] Context akhir terbentuk sebagai JSON terstruktur.

---

### 24.2 AI Reasoning Acceptance

- [ ] AWS Bedrock menghasilkan output JSON valid.
- [ ] Output mengandung `recommended_qty`, `confidence_score`, `risk_level`, dan `reasoning_narrative`.
- [ ] Reasoning narrative menggunakan Bahasa Indonesia.
- [ ] Penjelasan menyebut variabel utama seperti stok, lead time, cuaca, promo, dan kalender.
- [ ] Output tidak valid memicu retry.
- [ ] Jika tetap gagal, fallback rule-based digunakan.
- [ ] Prompt version dicatat di audit log.

---

### 24.3 Business Logic Acceptance

- [ ] MOQ diterapkan dengan benar.
- [ ] Packaging multiple diterapkan dengan benar.
- [ ] SKU perishable mendapat perlindungan lebih konservatif.
- [ ] Cold start ditandai dan confidence diturunkan.
- [ ] Missing data ditandai dan tidak menyebabkan sistem crash.
- [ ] Feedback rejection/edit disimpan.

---

### 24.4 Telegram Acceptance

- [ ] Kartu Telegram menampilkan toko, SKU, stok, threshold, lead time, cuaca, narasi AI, dan rekomendasi.
- [ ] Tombol Approve, Ubah Jumlah, dan Tolak berfungsi.
- [ ] Approve memicu proses pembuatan PR SAP.
- [ ] Edit qty meminta input baru dan validasi berjalan.
- [ ] Reject meminta alasan dan menyimpan feedback.
- [ ] Timeout menghasilkan status `TIMEOUT`.
- [ ] Duplicate click tidak membuat PR ganda.

---

### 24.5 SAP Integration Acceptance

- [ ] PR dibuat hanya setelah approval valid.
- [ ] Payload SAP sesuai struktur OData.
- [ ] SAP response disimpan di audit log.
- [ ] SAP failure menghasilkan status `FAILED_SAP`.
- [ ] Error SAP dapat ditampilkan di dashboard.
- [ ] Tidak ada PR duplikat.
- [ ] Credentials tidak muncul di log.

---

### 24.6 Dashboard Acceptance

- [ ] Dashboard menampilkan Multi-Store Inventory Health.
- [ ] Dashboard menampilkan Agent Reasoning Trace & Audit Log.
- [ ] Dashboard menampilkan SAP Integration Monitor.
- [ ] Dashboard menampilkan Feedback Analytics.
- [ ] Data dapat difilter berdasarkan toko, tanggal, SKU, dan status.
- [ ] Akses dashboard dibatasi berdasarkan role.

---

### 24.7 Security and Observability Acceptance

- [ ] Secrets disimpan di AWS Secrets Manager.
- [ ] IAM role menggunakan least privilege.
- [ ] DynamoDB encryption at rest aktif.
- [ ] Semua komunikasi eksternal menggunakan TLS.
- [ ] CloudWatch logs tersedia.
- [ ] Alert untuk error kritis tersedia.
- [ ] Tidak ada secret exposure di log atau frontend.

---

## 25. AI ANTIGRAVITY EXECUTION INSTRUCTIONS

Bagian ini memberikan instruksi langsung untuk AI Antigravity atau AI agent lain yang membantu implementasi AutoReplenish.ai.

Gunakan PRD ini sebagai source of truth. Jika ada konflik antara instruksi teknis dan prinsip produk, utamakan:

1. Human governance.
2. Auditability.
3. Keamanan.
4. Explainability.
5. Pencegahan stockout dan overstock.

---

### 25.1 Execution Order

Kecuali diminta sebaliknya, eksekusi dilakukan dengan urutan berikut:

#### Step 1 — Infrastructure Blueprint

Generate Infrastructure as Code untuk:

- DynamoDB table.
- IAM roles.
- Lambda functions.
- EventBridge scheduler.
- Secrets Manager references.
- CloudWatch log groups.
- API Gateway untuk dashboard.
- Dead Letter Queue.

**Preferred Output:**

- Terraform, atau
- AWS CloudFormation, atau
- Architecture specification jika IaC tidak diminta.

**Constraints:**

- Gunakan least privilege IAM.
- Pisahkan role per Lambda.
- Aktifkan DynamoDB TTL untuk cache cuaca.
- Jangan hardcode secrets.

---

#### Step 2 — Backend Orchestration

Generate Python Lambda code untuk:

- Scheduled SKU evaluation.
- SKU prioritization.
- Context aggregation.
- Weather caching.
- Bedrock invocation.
- JSON validation.
- MOQ adjustment.
- Packaging adjustment.
- Audit logging.
- Telegram send message.

**Constraints:**

- Gunakan Python 3.11+.
- Gunakan boto3.
- Gunakan structured logging.
- Gunakan idempotency key.
- Jangan mengirim raw Bedrock output ke Telegram tanpa validasi.

---

#### Step 3 — Telegram Webhook

Generate webhook handler untuk:

- Parsing callback button.
- Validasi state.
- Approve action.
- Edit flow.
- Reject flow.
- Timeout prevention.
- Duplicate click prevention.
- Input validation untuk qty manual.

**Constraints:**

- Gunakan state DynamoDB.
- Jangan membuat PR jika status tidak valid.
- Simpan semua aksi user.
- Gunakan HTTPS.

---

#### Step 4 — SAP Integration

Generate SAP integration module untuk:

- Token retrieval.
- OData read.
- OData write.
- Error handling.
- Retry.
- Idempotency.
- Payload mapping.
- SAP response logging.

**Constraints:**

- Credentials dari Secrets Manager.
- Timeout dan retry harus jelas.
- PR hanya dibuat setelah approval.
- Response SAP harus disimpan.

---

#### Step 5 — Dashboard API and UI

Generate:

- API Gateway endpoints.
- Lambda read-only handlers.
- React components.
- Inventory health page.
- Audit trace page.
- SAP monitor page.
- Feedback analytics page.

**Constraints:**

- Dashboard bersifat read-only terhadap data utama.
- Gunakan role-based access.
- Jangan tampilkan secret.
- Tampilkan prompt version dan trace lengkap.

---

#### Step 6 — Testing

Generate:

- Unit tests.
- Integration tests.
- Mock SAP responses.
- Mock Bedrock responses.
- Mock Telegram updates.
- End-to-end test scenario.

**Constraints:**

- Test MOQ rounding.
- Test invalid Bedrock output.
- Test duplicate approve.
- Test timeout.
- Test SAP failure.
- Test weather cache fallback.

---

### 25.2 AI Antigravity Task Prompt Template

Gunakan prompt berikut jika ingin meminta AI Antigravity menghasilkan deliverable spesifik:

```text
You are implementing AutoReplenish.ai based on the attached PRD.

Your task is:
1. Read the PRD fully.
2. Focus on Section [SECTION_NUMBER].
3. Generate production-ready [OUTPUT_TYPE].
4. Use AWS serverless stack and SAP S/4HANA integration constraints defined in the PRD.
5. Do not introduce new platforms or dependencies unless required.
6. Output must be complete, executable, and aligned with the PRD.

Current task:
[TASK_DESCRIPTION]
```

**Example:**

```text
You are implementing AutoReplenish.ai based on the attached PRD.

Your task is:
1. Read the PRD fully.
2. Focus on Section 21 and Section 25.
3. Generate production-ready Terraform for DynamoDB, IAM roles, Lambda functions, EventBridge scheduler, Secrets Manager references, CloudWatch log groups, API Gateway, and DLQ.
4. Use AWS serverless stack and SAP S/4HANA integration constraints defined in the PRD.
5. Do not introduce new platforms or dependencies unless required.
6. Output must be complete, executable, and aligned with the PRD.

Current task:
Create Terraform infrastructure blueprint for AutoReplenish.ai Phase 1 Production Foundation.
```

---

### 25.3 Output Expectations

Setiap output dari AI Antigravity sebaiknya mengandung:

1. **File structure**
   - Daftar file yang dibuat atau diubah.

2. **Code**
   - Kode siap pakai atau pseudo-code yang cukup jelas.

3. **Configuration**
   - Environment configuration, IAM policy, atau schema jika relevan.

4. **Testing**
   - Unit test atau integration test minimum.

5. **Notes**
   - Asumsi, dependency, dan langkah berikutnya.

---

## 26. DEFINITION OF TERMS

Berikut definisi istilah yang digunakan dalam dokumen ini.

| Term | Definition |
|---|---|
| Agentic AI | Sistem AI yang mampu melakukan penalaran multi-langkah berdasarkan konteks dan menghasilkan keputusan atau rekomendasi |
| Human-in-the-Loop | Pola desain di mana manusia tetap memberikan approval sebelum sistem mengambil aksi final |
| Stockout | Kondisi SKU tidak tersedia di rak/toko sehingga menyebabkan lost sales |
| Overstock | Kondisi stok berlebih melebihi kebutuhan wajar |
| Spoilage | Kerugian akibat barang rusak, tidak terjual, atau kedaluwarsa |
| Burn Rate | Rata-rata kecepatan konsumsi atau penjualan harian SKU |
| Lead Time | Waktu antara pemesanan dan barang tersedia di toko |
| MOQ | Minimum Order Quantity, jumlah minimum pemesanan ke DC/vendor |
| Packaging Multiple | Kelipatan kemasan yang harus dipenuhi, misalnya per dus |
| Purchase Requisition | Dokumen permintaan pembelian/pengadaan dalam SAP |
| Cold Start | Kondisi SKU atau toko baru memiliki data histori terbatas |
| Reasoning Trace | Jejak audit dari input AI, prompt, output, dan keputusan akhir |
| Feedback Loop | Mekanisme penyimpanan feedback manusia untuk memperbaiki rekomendasi berikutnya |
| Shadow Mode | Mode uji di mana AI memberi rekomendasi tanpa mengeksekusi dokumen SAP |
| Co-Pilot Mode | Mode di mana AI memberi rekomendasi dan manusia menyetujui sebelum eksekusi |
| Limited Automation | Mode otomatis terbatas untuk SKU low-risk dengan policy ketat |
| Full Autonomous Mode | Mode otomatis penuh tanpa approval per transaksi, bukan scope awal |
| Idempotency | Mekanisme untuk mencegah aksi duplikat jika request diulang |
| DLQ | Dead Letter Queue, antrian untuk message/event yang gagal diproses |
| TTL | Time to Live, mekanisme kedaluwarsa data otomatis di DynamoDB |

---

## 27. APPENDIX: SAMPLE TELEGRAM CARD

Berikut contoh kartu rekomendasi yang dikirim ke Kepala Toko melalui Telegram.

```text
📦 AUTOREPLENISH.AI — Rekomendasi Replenishment Stok

Toko: Cabang Sudirman (Area Perkantoran)
SKU: Roti Manis Cokelat 100g (Perishable)

Stok Fisik: 12 Pcs
Threshold: 20 Pcs
Lead Time: 2 Hari (tiba Minggu pagi)
Cuaca: Hujan deras (Sab–Min)

🧠 Analisis Agent (AWS Bedrock):
“Stok di bawah threshold, namun area perkantoran sepi saat weekend dan hujan deras menurunkan kunjungan — kuota dipotong 70% untuk mencegah overstock & kedaluwarsa.”

💡 Rekomendasi: 15 Pcs (1 Dus) — Normal: 50 Pcs

[✅ Approve & Kirim ke SAP]   [✏️ Ubah Jumlah]   [❌ Tolak]
```

---

### 27.1 Expected Behavior After Button Click

#### Approve

```text
✅ Rekomendasi disetujui.
Sistem sedang menerbitkan Purchase Requisition ke SAP S/4HANA.
```

Jika sukses:

```text
✅ Purchase Requisition berhasil dibuat.
PR ID: PR-4500012345
SKU: Roti Manis Cokelat 100g
Qty: 15 Pcs
```

#### Edit

```text
Masukkan jumlah baru untuk SKU Roti Manis Cokelat 100g.
Qty harus berupa angka positif dan memperhatikan kelipatan kemasan.
```

#### Reject

```text
Mohon tuliskan alasan penolakan rekomendasi ini.
Feedback akan digunakan untuk memperbaiki penalaran agen berikutnya.
```

---

## 28. APPENDIX: SAMPLE AUDIT RECORD

Berikut contoh audit record lengkap untuk satu keputusan AutoReplenish.ai.

```json
{
  "request_id": "REQ-20260616-0001",
  "run_id": "RUN-20260616-0500",
  "store_id": "STR-001",
  "store_name": "Cabang Sudirman",
  "area_type": "Perkantoran",
  "sku_id": "SKU-10023",
  "sku_name": "Roti Manis Cokelat 100g",
  "category": "Perishable",
  "physical_stock": 12,
  "threshold": 20,
  "average_daily_burn_rate": 25,
  "lead_time_days": 2,
  "moq": 12,
  "packaging_multiple": 12,
  "weather_condition": "Hujan deras",
  "weather_source": "cache",
  "weather_stale": false,
  "calendar_day": "Weekend",
  "is_public_holiday": false,
  "is_payday": false,
  "promo_active": false,
  "promo_type": null,
  "prompt_version": "v1.0",
  "model": "anthropic.claude-3-5-sonnet",
  "ai_recommended_qty": 15,
  "normal_qty": 50,
  "adjusted_qty_before_moq": 15,
  "final_recommended_qty": 15,
  "moq_applied": false,
  "packaging_multiple_applied": true,
  "confidence_score": 0.87,
  "risk_level": "medium",
  "reasoning_narrative": "Stok di bawah threshold, namun area perkantoran sepi saat weekend dan hujan deras menurunkan kunjungan — kuota dipotong 70% untuk mencegah overstock & kedaluwarsa.",
  "key_factors": [
    "below_threshold",
    "weekend_office_area_quiet",
    "heavy_rain",
    "perishable_sku",
    "lead_time_2_days"
  ],
  "warnings": [
    "SKU perishable dengan lead time 2 hari",
    "Permintaan weekend berisiko lebih rendah dari estimasi normal"
  ],
  "human_action": "APPROVED",
  "human_final_qty": 15,
  "rejection_reason": null,
  "sap_pr_status": "SUCCESS",
  "sap_pr_id": "PR-4500012345",
  "created_at": "2026-06-16T05:12:00+07:00",
  "approved_at": "2026-06-16T05:14:10+07:00",
  "completed_at": "2026-06-16T05:14:35+07:00"
}
```

---

### 28.1 Audit Traceability Requirement

Setiap audit record harus dapat menjawab pertanyaan berikut:

1. SKU apa yang direkomendasikan?
2. Toko mana yang menerima rekomendasi?
3. Konteks apa yang digunakan AI?
4. Prompt version apa yang digunakan?
5. Berapa rekomendasi awal AI?
6. Apakah qty disesuaikan karena MOQ atau kemasan?
7. Apa tindakan Kepala Toko?
8. Berapa qty final yang dikirim ke SAP?
9. Apakah PR SAP berhasil dibuat?
10. Jika gagal, apa penyebabnya?

---

## 29. FINAL PRODUCT PRINCIPLE

AutoReplenish.ai harus selalu diposisikan sebagai co-pilot replenishment yang transparan, explainable, dan berada dalam kendali manusia, bukan sebagai black-box automation yang menggantikan Kepala Toko.

Produk ini harus memenuhi prinsip berikut:

### 29.1 Practical

Sistem harus langsung berguna bagi Kepala Toko dan tim regional. Rekomendasi harus jelas, ringkas, dan dapat ditindaklanjuti.

### 29.2 Explainable

Setiap rekomendasi harus memiliki narasi yang dapat dipahami manusia. Kepala Toko harus mengerti mengapa AI merekomendasikan jumlah tertentu.

### 29.3 Auditable

Setiap keputusan harus dapat ditelusuri dari data awal, prompt AI, output AI, aksi manusia, hingga dokumen SAP.

### 29.4 Integrated with SAP

SAP S/4HANA tetap menjadi system of record. AutoReplenish.ai tidak boleh membuat sumber kebenaran baru yang menyalahi SAP.

### 29.5 Easy for Store Managers

Interface utama Kepala Toko adalah Telegram. Alur harus sederhana, cepat, dan tidak menambah beban administratif.

### 29.6 Scalable Across Branches

Arsitektur serverless harus mampu menambah toko baru tanpa menambah beban tim pusat secara signifikan.

### 29.7 Conservative for Perishable

Untuk SKU perishable, sistem harus lebih mengutamakan pencegahan spoilage dan overstock.

### 29.8 Efficient in Cloud Cost

Sistem harus menggunakan caching, batching, dan prioritas SKU agar biaya Bedrock, Lambda, DynamoDB, dan API eksternal terkendali.

### 29.9 Ready for Pilot-to-Production Rollout

Produk harus dapat diuji melalui shadow mode, co-pilot mode, dan limited automation sebelum otomatisasi penuh dipertimbangkan.

### 29.10 Human Governance First

Pada fase awal, tidak ada Purchase Requisition SAP yang boleh dibuat tanpa approval manusia, kecuali SKU masuk dalam policy limited automation yang disetujui.

---

## 30. END OF PRD

Dokumen ini merupakan PRD lengkap untuk AutoReplenish.ai dan siap digunakan sebagai input untuk AI Antigravity, tim engineering, tim produk, tim SAP, dan stakeholder bisnis.

**Ringkasan Akhir:**

- Produk: AutoReplenish.ai.
- Domain: Agentic AI untuk replenishment minimarket.
- Core Stack: AWS Bedrock, AWS Lambda, Amazon EventBridge, Amazon DynamoDB, SAP S/4HANA, Telegram Bot, React.js.
- Prinsip utama: Context-aware reasoning, human-in-the-loop, auditability, semi-autonomous execution.
- Fokus bisnis: Mengurangi stockout, mengurangi overstock/spoilage, meningkatkan efisiensi modal kerja, dan meningkatkan efisiensi Kepala Toko.
- Status MVP: Empat fase hackathon telah selesai dan menghasilkan MVP fungsional.
- Langkah berikutnya: Production foundation, reasoning hardening, human-in-the-loop optimization, dashboard auditability, dan pilot rollout.

**Arah Eksekusi untuk AI Antigravity:**

1. Gunakan PRD ini sebagai source of truth.
2. Eksekusi bertahap dari infrastruktur ke backend, Telegram, SAP, dashboard, dan testing.
3. Jaga human governance, auditability, dan explainability.
4. Jangan menghasilkan rekomendasi atau otomatisasi yang tidak dapat diaudit.
5. Prioritaskan keamanan, idempotency, dan fallback yang aman.

**END OF DOCUMENT**