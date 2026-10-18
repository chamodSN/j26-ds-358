import json
from collections import Counter, defaultdict

import pandas as pd

from app.core.config import settings

WDC = settings.DATA_RAW_DIR / "WDC-Computers"
FILES = [
    WDC / "training" / "computers_train" / "computers_train_small.json.gz",
    WDC / "computers_gs.json.gz",
]


def as_dict(v):
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            d = json.loads(v)
            return d if isinstance(d, dict) else None
        except Exception:
            return None
    return None


offers = {}  # offer id -> dict of attributes (or None)
for path in FILES:
    df = pd.read_json(path, lines=True, compression="gzip")
    for side in ("left", "right"):
        for oid, kv in zip(df[f"id_{side}"], df[f"keyValuePairs_{side}"]):
            offers.setdefault(oid, as_dict(kv))

with_kv = {o: d for o, d in offers.items() if d}
key_counts, samples = Counter(), defaultdict(list)
for d in with_kv.values():
    for k, v in d.items():
        key_counts[k] += 1
        if len(samples[k]) < 3:
            samples[k].append(str(v)[:40])

print(f"unique offers: {len(offers)}")
print(f"offers with key-value pairs: {len(with_kv)} ({len(with_kv) / len(offers):.1%})")
if with_kv:
    print(f"avg attributes per such offer: {sum(len(d) for d in with_kv.values()) / len(with_kv):.1f}")
print(f"distinct attribute names: {len(key_counts)}")
print(f"names that appear only once: {sum(1 for c in key_counts.values() if c == 1)}")

print("\nTop 40 attribute names:")
for k, c in key_counts.most_common(40):
    print(f"  {c:>5}  {k!r:35} e.g. {samples[k]}")

print("\nVariants that look like memory / storage / cpu:")
for k, c in key_counts.most_common():
    if any(w in k.lower() for w in ("memory", "ram", "storage", "capacity", "cpu", "processor")):
        print(f"  {c:>5}  {k!r:35} e.g. {samples[k]}")