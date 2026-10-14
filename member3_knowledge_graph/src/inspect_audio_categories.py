
from pathlib import Path
import csv

# Locate the M3 data folder
project_dir = Path(__file__).resolve().parent.parent
taxonomy_file = project_dir / "data" / "electronics_taxonomy.csv"

# Search terms to inspect relevant categories
keywords = [
    "headphone",
    "earbud",
    "earphone",
    "audio",
    "speaker",
    "soundbar",
    "microphone",
    "bluetooth"
]

print("\nGOOGLE ELECTRONICS TAXONOMY")
print("=" * 70)

matches = []

with open(taxonomy_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        category_name = row["category_name"].strip()
        category_path = row["category_path"].strip()

        searchable_text = (
            category_name + " " + category_path
        ).lower()

        if any(keyword in searchable_text for keyword in keywords):
            matches.append(row)

for row in matches:
    print(
        f"ID: {row['category_id']} | "
        f"Depth: {row['depth']}"
    )
    print(f"Category: {row['category_path']}")
    print("-" * 70)

print(f"\nTotal matching categories: {len(matches)}")
