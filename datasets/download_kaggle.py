"""Download development datasets for AutoReplenish.ai backtesting."""

from pathlib import Path
import os
import shutil

import kagglehub
from kagglehub import KaggleDatasetAdapter

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"


def download_competition(slug: str, folder_name: str) -> None:
    destination = RAW / folder_name
    destination.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {slug} ...")
    downloaded = Path(kagglehub.competition_download(slug))
    if downloaded.resolve() != destination.resolve():
        if downloaded.is_dir():
            for item in downloaded.iterdir():
                target = destination / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
        else:
            shutil.copy2(downloaded, destination / downloaded.name)
    print(f"Saved under: {destination}")


def load_walmart_sample() -> None:
    file_path = os.getenv("WALMART_FILE_PATH", "").strip()
    if not file_path:
        print("Skipping Walmart pandas load: set WALMART_FILE_PATH, e.g. train.csv")
        return
    output_dir = RAW / "walmart-sales-forecast"
    output_dir.mkdir(parents=True, exist_ok=True)
    dataframe = kagglehub.load_dataset(
        KaggleDatasetAdapter.PANDAS,
        "aslanahmedov/walmart-sales-forecast",
        file_path,
    )
    output_file = output_dir / (Path(file_path).stem + ".parquet")
    dataframe.to_parquet(output_file, index=False)
    print(f"Saved Walmart sample: {output_file}")
    print(dataframe.head())


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    download_competition("favorita-grocery-sales-forecasting", "favorita-grocery-sales-forecasting")
    download_competition("m5-forecasting-accuracy", "m5-forecasting-accuracy")
    download_competition("rossmann-store-sales", "rossmann-store-sales")
    load_walmart_sample()
    print("Dataset download process complete.")


if __name__ == "__main__":
    main()
