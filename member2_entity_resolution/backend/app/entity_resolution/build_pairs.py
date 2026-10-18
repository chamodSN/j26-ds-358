import json

import numpy as np
import pandas as pd

from app.core.config import settings
from app.entity_resolution.blocking import blocking_metrics, top_k_candidates
from app.entity_resolution.datasets import load_records
from app.entity_resolution.embeddings import embed_records_cached
from app.entity_resolution.preprocessing import DATASETS

SEARCH_K = 50


def group_split(left_ids, seed: int) -> dict:
    """70/15/15 split by LEFT record, so one left record never appears in two splits."""
    rng = np.random.default_rng(seed)
    ids = np.array(sorted(set(left_ids)))
    rng.shuffle(ids)
    n_tr, n_va = int(0.70 * len(ids)), int(0.15 * len(ids))
    return {
        lid: "train" if i < n_tr else ("val" if i < n_tr + n_va else "test")
        for i, lid in enumerate(ids)
    }


def build(name: str, cfg: dict):
    records = load_records(name)
    emb = embed_records_cached(records, name)
    lmask = (records["source"] == cfg["left"]["source"]).values
    rmask = (records["source"] == cfg["right"]["source"]).values
    left_ids = records.loc[lmask, "record_id"].tolist()
    right_ids = records.loc[rmask, "record_id"].tolist()

    _, idx = top_k_candidates(emb[lmask], emb[rmask], SEARCH_K)

    matches = pd.read_csv(settings.DATA_INTERIM_DIR / f"{name}_matches.csv", dtype=str)
    true_pairs = list(zip(matches["left_id"], matches["right_id"]))
    true_set = set(true_pairs)

    metrics = blocking_metrics(left_ids, right_ids, idx, true_pairs)
    print(f"\n=== {name}: {len(left_ids)} left x {len(right_ids)} right, {len(true_pairs)} true matches ===")
    for k, m in metrics.items():
        print(f"  K={k:>2}: pair completeness={m['pair_completeness']:.3f}  reduction ratio={m['reduction_ratio']:.3f}")

        K = settings.BLOCKING_TOP_K
    rows = [
        (lid, right_ids[j], int((lid, right_ids[j]) in true_set))
        for i, lid in enumerate(left_ids)
        for j in idx[i, :K]
    ]
    pairs = pd.DataFrame(rows, columns=["left_id", "right_id", "label"])
    pairs["blocked"] = 1
    split_map = group_split(left_ids, settings.RANDOM_SEED)
    pairs["split"] = pairs["left_id"].map(split_map)

    found = int(pairs["label"].sum())
    print(f"  candidate pairs at K={K}: {len(pairs)} | true matches found: {found}/{len(true_pairs)} | missed by blocking: {len(true_pairs) - found}")

    # true matches that blocking missed: kept in the file, flagged blocked=0
    cand = set(zip(pairs["left_id"], pairs["right_id"]))
    missed = [(l, r) for l, r in true_pairs if (l, r) not in cand]
    missed_df = pd.DataFrame(missed, columns=["left_id", "right_id"])
    missed_df["label"] = 1
    missed_df["blocked"] = 0
    missed_df["split"] = missed_df["left_id"].map(split_map)
    pairs = pd.concat([pairs, missed_df], ignore_index=True)
    print(pairs.groupby("split")["label"].agg(pairs="size", matches="sum").to_string())

    settings.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(settings.DATA_PROCESSED_DIR / f"{name}_pairs.csv", index=False)
    with open(settings.RESULTS_DIR / f"{name}_blocking.json", "w") as f:
        json.dump({"n_true": len(true_pairs), "metrics": metrics}, f, indent=2)


if __name__ == "__main__":
    for name, cfg in DATASETS.items():
        build(name, cfg)