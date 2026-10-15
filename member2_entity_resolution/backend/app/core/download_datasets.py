"""
Downloads and unzips the Abt-Buy and Amazon-GoogleProducts benchmark datasets
from the Leipzig Database Group's official entity-resolution benchmark page.
"""
import requests
import zipfile
import io
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.config import settings

DATASETS = {
    "Abt-Buy": "https://dbs.uni-leipzig.de/files/datasets/Abt-Buy.zip",
    "Amazon-GoogleProducts": "https://dbs.uni-leipzig.de/files/datasets/Amazon-GoogleProducts.zip",
}

def download_and_extract(name: str, url: str, dest_dir: Path):
    print(f"Downloading {name}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    target = dest_dir / name
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(target)
    print(f"  -> extracted to {target}")

if __name__ == "__main__":
    settings.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in DATASETS.items():
        download_and_extract(name, url, settings.DATA_RAW_DIR)
    print("\nDone. Each folder contains two source CSVs + one perfect-mapping CSV.")
    print("NOTE: WDC Product Corpus must be downloaded manually —")
    print("go to https://webdatacommons.org/largescaleproductcorpus/ and")
    print("pick the category subset closest to electronics (e.g. computers).")