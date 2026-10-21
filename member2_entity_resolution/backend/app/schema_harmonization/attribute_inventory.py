"""Step 1 of Novelty 2: collect every attribute NAME seen in the data, with how often it
occurs and a few sample VALUES (the values are what disambiguate e.g. 'Capacity').

  python -m app.schema_harmonization.attribute_inventory
"""
import ast
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import settings
from app.schema_harmonization.seed_schema import SEED_ATTRIBUTES

KVP_COLUMN = "key_value_pairs"
SAMPLE_SEP = " | "


def normalise_name(name) -> str:
    """'Memory Type *' / 'memory-type' -> 'memory type'"""
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()


def parse_kvp(raw) -> dict:
    """Tolerant parser: dict, JSON string, Python-repr string, list of pairs, or empty."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return {}
    d = raw
    if not isinstance(raw, (dict, list)):
        s = str(raw).strip()
        if not s or s.lower() in ("nan", "none", "null", "{}", "[]"):
            return {}
        try:
            d = json.loads(s)
        except Exception:
            try:
                d = ast.literal_eval(s)
            except Exception:
                return {}
    if isinstance(d, list) and all(isinstance(x, (list, tuple)) and len(x) == 2 for x in d):
        d = dict(d)
    if not isinstance(d, dict):
        return {}
    out = {}
    for k, v in d.items():
        k = str(k).strip()
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            v = " / ".join(map(str, v))
        v = str(v).strip()
        if k and v and v.lower() not in ("null", "none", "nan"):
            out[k] = v
    return out


def build_inventory(records: pd.DataFrame, column: str = KVP_COLUMN) -> pd.DataFrame:
    count, raw_names, values = Counter(), defaultdict(Counter), defaultdict(Counter)
    for raw in records[column]:
        seen = set()
        for k, v in parse_kvp(raw).items():
            n = normalise_name(k)
            if not n or n in seen:
                continue
            seen.add(n)
            count[n] += 1
            raw_names[n][k] += 1
            values[n][v[:60]] += 1
    rows = [dict(name_norm=n, display_name=raw_names[n].most_common(1)[0][0], count=c,
                 samples=[v for v, _ in values[n].most_common(3)])
            for n, c in count.items()]
    df = pd.DataFrame(rows)
    return df.sort_values(["count", "name_norm"], ascending=[False, True]).reset_index(drop=True)


def save_inventory(df: pd.DataFrame, path: Path):
    out = df.copy()
    out["samples"] = out["samples"].apply(lambda s: SAMPLE_SEP.join(s))
    out.to_csv(path, index=False)


def load_inventory(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, keep_default_na=False)
    df["samples"] = df["samples"].apply(lambda s: [x for x in str(s).split(SAMPLE_SEP) if x])
    return df


def seed_alias_names() -> set:
    return {normalise_name(a) for spec in SEED_ATTRIBUTES.values() for a in spec["aliases"]}


def make_gold_template(inv: pd.DataFrame, path: Path, n_frequent=60, n_rare=40, seed=42):
    """Random sample to hand-label. Names that exactly equal a seed alias are excluded
    (they are handled by the deterministic alias lookup, not by the embedding)."""
    pool = inv[~inv["name_norm"].isin(seed_alias_names())]
    freq = pool[pool["count"] >= 3]
    rare = pool[pool["count"] < 3]
    parts = [freq.sample(min(n_frequent, len(freq)), random_state=seed),
             rare.sample(min(n_rare, len(rare)), random_state=seed)]
    t = pd.concat(parts).sort_values("count", ascending=False)
    t = t[["name_norm", "display_name", "count", "samples"]].copy()
    t["samples"] = t["samples"].apply(lambda s: SAMPLE_SEP.join(s))
    t["gold"] = ""
    t.to_csv(path, index=False)
    return len(t)


def main():
    from app.entity_resolution.datasets import load_records
    records = load_records("wdc")
    if KVP_COLUMN not in records.columns:
        raise SystemExit(f"Column '{KVP_COLUMN}' not found. Columns: {list(records.columns)}")

    inv = build_inventory(records)
    interim = Path(settings.DATA_INTERIM_DIR)
    save_inventory(inv, interim / "attribute_inventory.csv")

    with_kv = int((records[KVP_COLUMN].apply(lambda r: len(parse_kvp(r)) > 0)).sum())
    print(f"Records: {len(records)}   with attributes: {with_kv} ({with_kv / len(records):.1%})")
    print(f"Distinct attribute names: {len(inv)}   seen >=5 times: {(inv['count'] >= 5).sum()}   "
          f"singletons: {(inv['count'] == 1).sum()}")
    print("\nTop 15 attribute names:")
    for r in inv.head(15).itertuples():
        print(f"  {r.count:5d}  {r.display_name:28s} {SAMPLE_SEP.join(r.samples)[:60]}")

    gold_tpl = interim / "schema_gold_template.csv"
    if gold_tpl.exists():
        print(f"\n{gold_tpl.name} already exists - NOT overwritten (your labels are safe).")
    else:
        n = make_gold_template(inv, gold_tpl)
        print(f"\nWrote {n} names to label: {gold_tpl}")
    print("\nSeed attribute ids (use these in the 'gold' column):")
    print("  " + ", ".join(SEED_ATTRIBUTES))


if __name__ == "__main__":
    main()