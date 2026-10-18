
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "amazon_electronics_categories.json"

with INPUT_FILE.open("r", encoding="utf-8") as file:
    categories = json.load(file)

print(f"Total category paths: {len(categories)}")

print("\nFirst 25 category paths:")
for item in categories[:25]:
    print(" > ".join(item["path"]))

print("\nTop-level categories:")
top_level = Counter(
    item["path"][0]
    for item in categories
    if item.get("path")
)

for name, count in top_level.most_common():
    print(f"{name}: {count}")

print("\nExample PP1-related categories:")
keywords = [
    "phone", "mobile", "cell", "computer", "laptop",
    "tablet", "watch", "memory", "ssd", "hard drive",
    "processor", "graphics", "camera", "television",
    "speaker", "headphone", "router", "cable", "fan"
]

matches = [
    item for item in categories
    if any(
        keyword in " > ".join(item["path"]).lower()
        for keyword in keywords
    )
]

for item in matches[:60]:
    print(" > ".join(item["path"]))

print(f"\nTotal keyword-matched paths: {len(matches)}")
