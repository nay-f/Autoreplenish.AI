# 📋 LAPORAN EVALUASI & TINJAUAN ARSITEKTUR: AutoReplenish.ai

**Tanggal:** 27 Oktober 2026  
**Status Dokumen:** Rekomendasi Arsitektur & Desain Metrik Dashboard  
**Penyusun:** Antigravity Cognitive Engineering  

---

## 1. Ringkasan Eksekutif

Dokumen ini disusun sebagai hasil diskusi mendalam (*architectural review*) untuk menjawab 4 pilar pertanyaan strategis AutoReplenish.ai:
1. **Kesiapan Agen AI**: Apakah sistem saat ini sudah menjadi agen yang sesuai atau masih butuh dataset khusus (*fine-tuning*) untuk model AI-nya?
2. **Dataset Industri Ritel**: Apakah ada dataset dunia nyata yang sesuai dengan ide rantai pasok AutoReplenish.ai?
3. **Fungsi Riil SAP**: Apakah benar kegunaan SAP hanya sebagai database saja?
4. **Desain Tampilan Akurasi Dashboard**: Bagaimana cara menghitung dan menampilkan persentase akurasi AI secara objektif pada Dashboard manajerial?

---

## 2. Evaluasi AI Agent: Mengapa Model Saat Ini Sudah Sesuai Tanpa Fine-Tuning

### A. Kondisi Arsitektur Saat Ini
AutoReplenish.ai saat ini mengadopsi pola **Cognitive Reasoning Agent** berbasis **AWS Bedrock (Claude 3.5 Sonnet)** yang dipadukan dengan **Deterministic Guardrail (Python)**:
* `backend/src/services/bedrock_service.py`: Menggunakan *System Prompt* berbasis prinsip Pareto 80/20 dan *In-Context Data Injection* yang menyuplai data live (stok, laju konsumsi, lead time, cuaca lokal, siklus kalender gajian, promo aktif).
* `backend/src/services/moq_packaging_service.py`: Mengunci pembulatan kelipatan karton dan MOQ (*Minimum Order Quantity*) dengan matematika deterministik.

### B. Mengapa Fine-Tuning LLM TIDAK Dibutuhkan (Bahkan Berisiko)?
| Faktor Risiko | Pendekatan Fine-Tuning Model LLM | Pendekatan In-Context RAG (Saat Ini) |
| :--- | :--- | :--- |
| **Kalkulasi Numerik** | **Tinggi Risiko Halusinasi**: LLM memproses teks berbasis token sub-kata. Melatih LLM pada ribuan baris deret angka deret waktu tabular sering memicu *numerical hallucination* (salah hitung penjumlahan/kelipatan). | **Aman**: LLM hanya melakukan penalaran sebab-akibat (*reasoning*), sedangkan pembulatan fisik dan kelipatan dihitung oleh kode pasti Python. |
| **Kecepatan Perubahan Data (*Data Drift*)** | **Lambat & Mahal**: Stok fisik, promo mingguan, dan katalog toko ritel berubah terus-menerus. Melakukan fine-tuning ulang model setiap minggu menghabiskan biaya komputasi GPU yang sangat besar. | **Real-Time (Zero Latency Context)**: Perubahan data stok dan cuaca langsung masuk sebagai variabel *payload prompt* detik itu juga tanpa perlu *retraining*. |
| **Kualitas Bahasa (*Catastrophic Forgetting*)** | **Rentan Rusak**: Memaksa LLM mempelajari matriks angka tabular sering merusak keluwesan bahasa aslinya, sehingga narasi alasan rekomendasi di Telegram menjadi kaku atau tidak logis. | **Optimal**: Mempertahankan kecerdasan bahasa Claude 3.5 Sonnet untuk menyusun narasi sebab-akibat yang dapat dipahami Kepala Toko (*Explainable AI*). |
| **Transparansi Audit** | **Kotak Hitam (*Black Box*)**: Sulit diaudit mengapa bobot neuron model memilih angka tertentu. | **100% Traceable**: Semua input konteks dan argumen penalaran tersimpan lengkap di audit trail DynamoDB. |

**Kesimpulan Pilar 1**: Arsitektur agen saat ini **sudah sangat sesuai standar modern**. Agen tidak membutuhkan fine-tuning model LLM, melainkan pengayaan konteks dinamis (*In-Context RAG*).

---

## 3. Kajian Dataset Benchmark Industri Ritel

Terdapat dataset publik skala enterprise di Kaggle yang merepresentasikan karakteristik rantai pasok AutoReplenish.ai:

| Nama Dataset | Sumber Data | Skala & Karakteristik | Relevansi Fitur dengan AutoReplenish.ai |
| :--- | :--- | :--- | :--- |
| **M5 Forecasting - Accuracy** | Walmart & Makridakis Center (Kaggle) | 30.490 SKU, 10 toko ritel, 5+ tahun data harian | Memuat variabel siklus hari gajian/bantuan pangan (`snap_CA/TX/WI`), promo mingguan, dan hari raya nasional. |
| **Corporación Favorita Grocery** | Jaringan Supermarket Favorita (Kaggle) | >200.000 SKU, 54 toko swalayan | Memiliki penanda krusial **barang mudah rusak (`is_perishable`)**, kalender libur lokal, dan promo berjalan (`onpromotion`). |
| **Walmart Store Sales Forecasting** | Walmart Recruiting (Kaggle) | 45 gerai ritel Walmart | Memasukkan anomali cuaca lokal harian (**temperature**) dan variasi diskon markdown. |
| **Rossmann Store Sales** | 1.115 Toko Ritel Rossmann (Kaggle) | Penjualan harian ribuan cabang | Memuat pengaruh promosi berkelanjutan (`Promo` & `Promo2`) serta jarak kompetitor ritel terdekat. |

### Peran Tepat Dataset Tersebut untuk AutoReplenish.ai:
* ❌ **Bukan untuk melatih bobot model LLM.**
* ✅ **Digunakan sebagai Data Uji (*Backtesting & Benchmark Simulation*)**: Sangat berguna untuk menguji simulator di dashboard dan membuktikan akurasi formula sebelum dideploy ke gerai fisik riil.

---

## 4. Dekonstruksi Peran SAP: Enterprise ERP vs Database

### Apakah Benar SAP Hanya Berfungsi Sebagai Database?
**TIDAK BENAR.** Menganggap SAP hanya sebagai database adalah kesalahpahaman umum. Database hanyalah media penyimpanan data mentah, sedangkan SAP adalah **Sistem Tata Kelola Operasional Perusahaan (ERP)**.

```
┌─────────────────────────────────────────────────────────────┐
│                 Amazon DynamoDB (Database)                  │
│  - Menyimpan cache cuaca harian                             │
│  - Menyimpan state callback tombol Telegram (Pending/Done)  │
│  - Menyimpan audit log & riwayat interaksi raw JSON         │
└──────────────────────────────────────┬──────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 SAP S/4HANA (Enterprise ERP)                │
│  - Validasi Pagu Anggaran Toko (Budget Governance)          │
│  - Menjaga Master Data Kontrak Vendor & SLA Distributor     │
│  - Eksekusi Dokumen Resmi: Purchase Requisition (PR) ke PO  │
│  - Proses 3-Way Matching (PO vs Penerimaan Barang vs Faktur)│
└─────────────────────────────────────────────────────────────┘
```

### Mengapa Integrasi SAP di AutoReplenish.ai Krusial?
1. **Otorisasi Resmi Rantai Pasok**: Saat Kepala Toko menekan `✅ Setujui` di Telegram, endpoint `sap_service.create_purchase_requisition` menerbitkan dokumen Purchase Requisition standar OData (`API_PURCHASEREQ_PROCESS_SRV`). Dokumen ini memiliki nomor registrasi audit legal perusahaan ritel.
2. **Kepatuhan Finansial**: Transaksi pengadaan yang disetujui otomatis masuk ke pencatatan akuntansi komitmen belanja perusahaan, mencegah pemesanan fiktif atau melebihi plafon modal kerja.

---

## 5. Desain Tampilan Akurasi Khusus untuk Dashboard Manajerial

Sesuai arahan, metrik akurasi akan difokuskan **hanya pada Dashboard** agar pimpinan operasional dan manajer rantai pasok dapat memantau efektivitas AI secara transparan tanpa mengubah kode yang ada saat ini.

### A. Tiga Indikator Akurasi Utama yang Direkomendasikan

#### 1. Forecast Accuracy / WAPE-Inverse (%)
* **Definisi**: Mengukur seberapa tepat kuota rekomendasi AI terhadap penjualan riil selama masa *lead time*.
* **Formula Standar Ritel**:
  $$\text{WAPE} = \frac{\sum |\text{Permintaan Aktual} - \text{Rekomendasi AI}|}{\sum \text{Permintaan Aktual}} \times 100\%$$
  $$\text{Forecast Accuracy} = 100\% - \text{WAPE}$$
* **Target Industri Ritel Modern**: **88% - 94%**.

#### 2. Human Acceptance Rate / Hit Rate (%)
* **Definisi**: Persentase rekomendasi AI yang langsung disetujui oleh Kepala Toko di Telegram tanpa penolakan atau revisi kuota manual.
* **Formula**:
  $$\text{Acceptance Rate} = \frac{\text{Jumlah Pesanan Disetujui (Approved)}}{\text{Total Rekomendasi Terbit}} \times 100\%$$
* **Fungsi**: Membuktikan tingkat kepercayaan operasional lapangan terhadap penalaran AI. Target: **> 90%**.

#### 3. Stockout & Spoilage Prevention Index (%)
* **Definisi**: Tingkat keberhasilan toko dalam menjaga stok tetap di atas batas kritis (*zero stockout*) sekaligus menekan pembusukan barang *perishable* (target PRD: penurunan *spoilage* hingga 50%).

---

### B. Mockup Komponen UI Dashboard (Konsep Visual)

Berikut adalah rancangan visual kartu metrik akurasi untuk panel atas (*Executive KPI Bar*) pada Dashboard:

```
┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
│ 🎯 FORECAST ACCURACY (AI) │ 🤝 HITL ACCEPTANCE RATE   │ 🛡️ SPOILAGE REDUCTION     │
├───────────────────────────┼───────────────────────────┼───────────────────────────┤
│          92.4%            │          95.1%            │          -51.2%           │
│   ▲ +3.2% vs baseline     │    (194 dari 204 disetujui)│   Target PRD tercapai     │
│  Metrik: 100% - WAPE 30h  │  Tingkat persetujuan TG   │   Penyusutan barang segar │
└───────────────────────────┴───────────────────────────┴───────────────────────────┘
```

---

### C. Skema Payload Data JSON untuk API Dashboard (Referensi Siap Pakai)

Frontend dashboard nantinya dapat mengonsumsi endpoint `/api/v1/metrics/accuracy` dengan struktur data berikut:

```json
{
  "period": "Last 30 Days",
  "summary": {
    "overall_accuracy_percentage": 92.4,
    "wape_error_rate": 7.6,
    "human_acceptance_rate": 95.1,
    "total_recommendations": 204,
    "approved_without_edit": 194,
    "edited_by_manager": 7,
    "rejected": 3
  },
  "accuracy_by_category": [
    {
      "category": "Ready-to-Drink (RTD)",
      "accuracy_percentage": 94.8,
      "primary_driver": "Korelasi cuaca suhu panas presisi tinggi"
    },
    {
      "category": "Fresh & Perishable",
      "accuracy_percentage": 90.1,
      "primary_driver": "Konservatif akhir pekan & shelf-life guardrail"
    },
    {
      "category": "Dry Groceries & Household",
      "accuracy_percentage": 93.5,
      "primary_driver": "Siklus stabil awal bulan (Payday)"
    }
  ],
  "confidence_distribution": {
    "high_confidence_above_90": 162,
    "medium_confidence_70_90": 38,
    "fallback_triggered": 4
  }
}
```

---

## 6. Kesimpulan & Status Akhir

1. **Kode dasar tetap utuh**: Tidak ada kode aplikasi atau file konfigurasi rahasia/`.env` yang diubah sesuai instruksi Anda.
2. **Arsitektur tervalidasi**: AutoReplenish.ai berada pada jalur arsitektur AI Agent terbaik (kombinasi kognitif LLM via AWS Bedrock + aturan operasional pasti MOQ + persetujuan manusia via Telegram + penerbitan dokumen resmi ERP SAP).
3. **Dokumen Tinjauan Tersedia**: Seluruh kajian dan konsep metrik akurasi dashboard telah didokumentasikan di file `review.md`.
