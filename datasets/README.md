# Dataset AutoReplenish.ai

Folder ini digunakan untuk dataset development/backtesting. Dataset di sini bukan database production dan tidak boleh berisi credential.

```text
datasets/
├── raw/
│   ├── favorita-grocery-sales-forecasting/
│   ├── m5-forecasting-accuracy/
│   ├── rossmann-store-sales/
│   └── walmart-sales-forecast/
├── processed/
├── reports/
└── download_kaggle.py
```

Install dependency dari root project:

```powershell
pip install kagglehub[pandas-datasets] pandas pyarrow
python datasets\download_kaggle.py
```

Untuk Walmart, set nama file yang benar dari dataset Kaggle:

```powershell
$env:WALMART_FILE_PATH="train.csv"
python datasets\download_kaggle.py
```

Dataset besar disimpan di `raw/` dan tidak di-commit ke Git. Script ini tidak menulis ke DynamoDB dan tidak memanggil Bedrock, Telegram, atau SAP.
