
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "category_crosswalk_candidates.json"

with INPUT_FILE.open("r", encoding="utf-8") as f:
    candidates = json.load(f)

print("CROSSWALK QUALITY REPORT")
print("=" * 50)
print(f"Total candidates: {len(candidates)}")

print("\nCandidates by status:")
for status, count in Counter(
    item.get("status", "missing") for item in candidates
).items():
    print(f"  {status}: {count}")

print("\nSimilarity score distribution:")
for score, count in sorted(
    Counter(item.get("similarity_score") for item in candidates).items(),
    reverse=True,
):
    print(f"  {score}: {count}")

pairs = [
    (item.get("amazon_id"), item.get("google_id"))
    for item in candidates
]
print(f"\nDuplicate pairs: {len(pairs) - len(set(pairs))}")

print("\nSample candidates for manual review:")
review = [
    item for item in candidates
    if item.get("status") == "manual_review"
]

for item in review[:15]:
    print(f"\nScore: {item.get('similarity_score')}")
    print(f"Amazon: {item.get('amazon_path')}")
    print(f"Google: {item.get('google_path')}")

print("\nUnverified candidates:",
      sum(not item.get("verified", False) for item in candidates))
