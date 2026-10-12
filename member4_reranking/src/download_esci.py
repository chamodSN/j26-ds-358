"""
Member 4 - Download the Amazon ESCI dataset.
Save as: member4_reranking/src/download_esci.py
Run from repo root:  python member4_reranking/src/download_esci.py

Downloads into member4_reranking/data/esci/ (gitignored).
Skips files that are already fully downloaded.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://github.com/amazon-science/esci-data/raw/main/shopping_queries_dataset/"
FILES = [
    "shopping_queries_dataset_examples.parquet",  # query-product pairs + E/S/C/I labels
    "shopping_queries_dataset_products.parquet",  # product title/description/brand... (large)
    "shopping_queries_dataset_sources.csv",       # query source info (small)
]
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "esci"


def remote_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req) as r:
        return int(r.headers.get("Content-Length", 0))


def download(url: str, dest: Path) -> None:
    size = remote_size(url)
    if dest.exists() and size and dest.stat().st_size == size:
        print(f"[skip] {dest.name} already downloaded ({size/1e6:.1f} MB)")
        return

    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"[get ] {dest.name} ({size/1e6:.1f} MB)")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if size:
                sys.stdout.write(f"\r       {done/1e6:8.1f} / {size/1e6:.1f} MB")
                sys.stdout.flush()
    print()
    if size and tmp.stat().st_size != size:
        raise RuntimeError(f"{dest.name}: incomplete download, run again")
    tmp.replace(dest)


def check(out: Path) -> None:
    """Quick sanity check: shapes and how many rows we will actually use."""
    try:
        import pandas as pd
    except ImportError:
        print("Install pandas + pyarrow to run the check: pip install pandas pyarrow")
        return
    ex = pd.read_parquet(out / FILES[0])
    pr = pd.read_parquet(out / FILES[1], columns=["product_id", "product_locale"])
    print("\nexamples:", ex.shape, list(ex.columns))
    print("products:", pr.shape)
    us_small = ex[(ex.product_locale == "us") & (ex.small_version == 1)]
    print("us + small_version=1 rows:", len(us_small))
    print(us_small.groupby("split").size().to_string())
    print("label counts:\n" + us_small.esci_label.value_counts().to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-check", action="store_true")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        download(BASE_URL + name, args.out / name)
    if not args.no_check:
        check(args.out)


if __name__ == "__main__":
    main()