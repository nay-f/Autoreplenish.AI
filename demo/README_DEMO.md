# 🚀 AutoReplenish.ai — Panduan Menjalankan Demo Lokal

Panduan lengkap untuk menjalankan demo end-to-end **AutoReplenish.ai** secara 100% lokal di komputer tanpa memerlukan akun AWS, tanpa cloud berbayar, dan tanpa kartu kredit.

---

## 🏗️ Arsitektur Sinkronisasi Data (Data Flow)

```
Telegram Bot (real API, long polling)
        │ (Klik Tombol Approve / Edit / Reject)
        ▼
Telegram Listener (04_telegram_listener.py)
        │ (Update Status, Simpan Feedback Log, Terbitkan PR)
        ▼
SQLite Database (demo/db/demo.db)
        ▲
        │ (Membaca data realtime)
Dashboard API (05_dashboard_api.py, FastAPI, Port 8000)
        ▲
        │ (Fetch API live data)
Dashboard React UI (Vite App, Port 3000)
```

| Komponen | Port / Path | Keterangan |
| :--- | :--- | :--- |
| **Telegram Bot** | Cloud (HTTPS) | Real Bot API via HTTPS Long Polling (`api.telegram.org`). |
| **Telegram Listener** | Python Script | Mendengarkan klik tombol & interaksi Telegram secara realtime. |
| **SQLite Database** | `demo/db/demo.db` | Single Source of Truth database lokal menggantikan DynamoDB. |
| **Dashboard API** | `http://localhost:8000` | REST API FastAPI yang menyajikan data realtime dari SQLite ke UI. |
| **Dashboard Web UI** | `http://localhost:3000` | React.js SPA Dashboard dengan charting dan audit trace interaktif. |

---

## 📋 1. Prasyarat Sistem

Pastikan komputer Anda sudah terpasang:
1. **Python 3.11+**
2. **Node.js 18+** (untuk menjalankan frontend React Dashboard)
3. **Koneksi Internet** (hanya untuk komunikasi bot dengan Telegram Bot API)
4. **Aplikasi Telegram** (Mobile atau Desktop)

---

## 🤖 2. Konfigurasi Telegram Bot & Chat ID

### A. Membuat Bot Telegram (@BotFather)
1. Buka Telegram dan cari akun resmi **`@BotFather`**.
2. Ketik `/newbot`, lalu ikuti petunjuk untuk memberi nama bot dan username (harus berakhiran `bot`, contoh: `AutoReplenishDemoBot`).
3. Salin **HTTP API Token** yang diberikan (format: `123456789:ABCDefghijk...`).

### B. Mendapatkan Chat ID Anda
1. Cari bot **`@userinfobot`** di Telegram dan klik **Start**.
2. Bot akan membalas dengan menampilkan **Id** Anda (contoh: `1181431005`).
3. **PENTING:** Buka bot yang baru Anda buat di langkah A, lalu klik tombol **START** agar bot memiliki izin mengirimkan pesan ke akun Telegram Anda.

### C. Mengisi File `.env`
Buka file `demo/.env` dan pastikan kedua variabel ini terisi:
```env
TELEGRAM_BOT_TOKEN=8992103055:AAE5awLLQOZkEO0rnDBp8RASbCqqiKvG6eE
TELEGRAM_CHAT_ID=1181431005
```

---

## ⚙️ 3. Instalasi Dependensi

### Backend Python:
```bash
cd demo
pip install -r requirements.txt
```

### Frontend Dashboard React:
```bash
cd dashboard
npm install
```

---

## 🎬 4. Urutan Menjalankan Demo Lengkap

### Langkah 1: Pre-Flight Check & Verifikasi Sinkronisasi
Jalankan verifikasi untuk memastikan sistem siap:
```bash
cd demo
python scripts/00_check_setup.py
python scripts/06_verify_sync.py
```
*Output yang diharapkan: Seluruh layer A, B, C, D bertanda hijau `✅`.*

---

### Langkah 2: Inisialisasi Database & Seeding
```bash
python scripts/01_init_db.py
python scripts/02_seed_demo.py
```

---

### Langkah 3: Jalankan Dashboard API (Terminal 1)
Buka **Terminal 1** dan jalankan REST API server:
```bash
cd demo
python scripts/05_dashboard_api.py
```
* Live API URL: [http://localhost:8000](http://localhost:8000)
* Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Langkah 4: Jalankan Telegram Interactive Listener (Terminal 2)
Buka **Terminal 2** dan jalankan listener tombol Telegram:
```bash
cd demo
python scripts/04_telegram_listener.py
```
> *Biarkan terminal ini tetap berjalan untuk menangkap aksi Approve / Edit / Reject dari Telegram.*

---

### Langkah 5: Jalankan React Dashboard UI (Terminal 3)
Buka **Terminal 3** dan jalankan web dashboard:
```bash
cd dashboard
npm run dev
```
* Buka browser di [http://localhost:3000](http://localhost:3000)

---

### Langkah 6: Trigger Evaluasi AI (Terminal 4 / Saat Presentasi)
Buka **Terminal 4** untuk mengirim rekomendasi replenishment ke Telegram:
```bash
cd demo
python scripts/03_run_pipeline.py
```
* **Hasil:** 4 kartu rekomendasi stok interaktif langsung terkirim ke Telegram Anda dan muncul di halaman **Agent Reasoning Trace** pada Dashboard Web [http://localhost:3000](http://localhost:3000).

---

## 📱 5. Skenario Pengujian Interaktif di Telegram & Dashboard

Saat kartu rekomendasi muncul di Telegram, Anda dapat mendemokan 3 skenario:

### Skenario A: Approve & Kirim ke SAP
1. Klik tombol **`✅ Approve & Kirim ke SAP`** di Telegram.
2. Bot akan membalas dengan **PR ID** resmi (misal: `PR-4500012341`).
3. Buka Dashboard Web ([http://localhost:3000](http://localhost:3000)), buka tab **SAP S/4HANA Monitor** dan **Reasoning Trace**. Status rekomendasi akan langsung berubah menjadi **APPROVED** dan daftar transaksi PR di SAP bertambah.
4. **Uji Idempotency:** Klik tombol `Approve` sekali lagi pada pesan yang sama. Sistem akan menolak duplikasi dan mencegah pembuatan PR ganda.

### Skenario B: Ubah Jumlah (Edit Quantity)
1. Klik tombol **`✏️ Ubah Jumlah`** di Telegram.
2. Ketik angka baru di chat Telegram (contoh: `24`), lalu balas **`YA`** untuk konfirmasi.
3. Bot menerbitkan PR ke SAP dengan jumlah 24 Pcs.
4. Di Dashboard Web, kolom **Keputusan Kepala Toko** pada tabel Reasoning Trace akan langsung terupdate menjadi **Diedit (24 Pcs)**.

### Skenario C: Tolak Rekomendasi (Reject & Feedback Loop)
1. Klik tombol **`❌ Tolak`** di Telegram.
2. Ketik alasan (misal: *"Stok gudang display masih mencukupi"*).
3. Bot membatalkan order dan menyimpan alasan.
4. Di Dashboard Web, buka tab **Feedback Analytics**. Tingkat Penolakan (*Rejection Rate*) dan grafik **Alasan Penolakan Paling Sering** akan langsung menampilkan alasan yang baru saja Anda ketik.

---

## 🛠️ Troubleshooting & FAQ

### 1. Dashboard di port 3000 tidak sinkron / menampilkan data mock?
* **Penyebab:** Frontend tidak dapat menghubungi backend di port 8000, sehingga mengaktifkan fallback mock.
* **Solusi:**
  1. Pastikan backend API sudah berjalan: `python scripts/05_dashboard_api.py`.
  2. Buka [http://localhost:8000/health](http://localhost:8000/health) di browser untuk memastikan API aktif.
  3. Pastikan file `dashboard/.env` berisi `VITE_API_BASE_URL=http://localhost:8000`.
  4. Jalankan `python scripts/06_verify_sync.py` untuk menguji kesehatan koneksi end-to-end.

### 2. Error: Telegram API Error: Unauthorized / Invalid Token
* Pastikan `TELEGRAM_BOT_TOKEN` di `demo/.env` sudah sesuai dengan token dari `@BotFather`.

### 3. Pesan tidak masuk ke Telegram
* Pastikan Anda sudah membuka bot Anda di Telegram dan menekan tombol **`START`**.
* Pastikan `TELEGRAM_CHAT_ID` sudah benar.
