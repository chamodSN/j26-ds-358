
from huggingface_hub import hf_hub_download
import pyarrow.parquet as pq
import json
from pathlib import Path

SHARD_COUNT = 10

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data"
OUTPUT_FILE = OUTPUT_DIR / "amazon_electronics_categories.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

unique_categories = set()
processed_products = 0

print("Starting Amazon Electronics category extraction...")

for shard_index in range(SHARD_COUNT):
    filename = (
        f"raw_meta_Electronics/full-{shard_index:05d}-of-00010.parquet"
    )

    print(f"\nProcessing shard {shard_index + 1}/{SHARD_COUNT}")

    try:
        file_path = hf_hub_download(
            repo_id="McAuley-Lab/Amazon-Reviews-2023",
            repo_type="dataset",
            filename=filename,
        )

        parquet_file = pq.ParquetFile(file_path)

        for batch in parquet_file.iter_batches(
            columns=["categories"],
            batch_size=5000,
        ):
            for row in batch.to_pylist():
                categories = row.get("categories") or []

                if not isinstance(categories, list):
                    continue

                for depth, category in enumerate(categories):
                    if not isinstance(category, str) or not category.strip():
                        continue

                    unique_categories.add(
                        tuple(categories[: depth + 1])
                    )

                processed_products += 1

        print(f"Products processed so far: {processed_products:,}")
        print(f"Unique category paths so far: {len(unique_categories):,}")

    except Exception as error:
        print(f"ERROR processing {filename}: {error}")
        raise

category_records = [
    {
        "path": list(path),
        "name": path[-1],
        "parent": path[-2] if len(path) > 1 else None,
        "depth": len(path) - 1,
    }
    for path in sorted(unique_categories)
]

with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(category_records, file, indent=2, ensure_ascii=False)

print("\nExtraction complete.")
print(f"Products processed: {processed_products:,}")
print(f"Unique category paths: {len(category_records):,}")
print(f"Output saved to: {OUTPUT_FILE}")
