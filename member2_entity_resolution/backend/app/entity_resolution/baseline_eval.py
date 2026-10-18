import json

import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.entity_resolution.datasets import load_pairs, load_records  # noqa: E402
from app.entity_resolution.embeddings import embed_records_cached  # noqa: E402

NAMES = ["abt_buy", "amazon_google", "wdc"]


def cosine_for_pairs(pairs, records, emb) -> np.ndarray:
    pos = {rid: i for i, rid in enumerate(records["record_id"])}
    li, ri = pairs["left_id"].map(pos), pairs["right_id"].map(pos)
    assert not li.isna().any() and not ri.isna().any(), "pair points to a record with no embedding"
    return (emb[li.astype(int).to_numpy()] * emb[ri.astype(int).to_numpy()]).sum(axis=1)


def prf(y, pred):
    p, r, f, _ = precision_recall_fscore_support(y, pred.astype(int), average="binary", zero_division=0)
    return float(p), float(r), float(f)


def predict(df, t):
    # a pair that blocking never retrieved can never be predicted a match
    return (df["cosine"].to_numpy() >= t) & (df["blocked"].to_numpy() == 1)


def best_threshold(df):
    y = df["label"].to_numpy()
    best_f, best_t = -1.0, 0.0
    for t in np.arange(0.30, 0.995, 0.005):
        f = prf(y, predict(df, t))[2]
        if f > best_f:
            best_f, best_t = f, float(t)
    return best_t, best_f


def run(name: str) -> dict:
    records = load_records(name)
    emb = embed_records_cached(records, name)
    pairs = load_pairs(name)
    if "blocked" not in pairs.columns:   # WDC pairs come pre-made, no blocking step
        pairs["blocked"] = 1
    pairs["cosine"] = cosine_for_pairs(pairs, records, emb)

    val, test = pairs[pairs["split"] == "val"], pairs[pairs["split"] == "test"]
    t, f_val = best_threshold(val)
    p, r, f = prf(test["label"].to_numpy(), predict(test, t))
    ceiling = float(test.loc[test["label"] == 1, "blocked"].mean())

    print(f"\n=== {name} (embedding-only baseline) ===")
    print(f"best single threshold on VAL = {t:.3f} (val F1 {f_val:.3f})")
    print(f"TEST at that threshold: precision={p:.3f} recall={r:.3f} F1={f:.3f}")
    print(f"recall ceiling from blocking on TEST: {ceiling:.3f}")

    hi, lo = settings.HIGH_CONFIDENCE_THRESHOLD, settings.LOW_CONFIDENCE_THRESHOLD
    cand = val[val["blocked"] == 1]
    tiers = pd.cut(cand["cosine"], [-1, lo, hi, 2], right=False,
                   labels=[f"low (<{lo})", f"mid [{lo},{hi})", f"high (>={hi})"])
    summary = cand.groupby(tiers, observed=False)["label"].agg(n="size", positives="sum")
    summary["positive_rate"] = (summary["positives"] / summary["n"]).round(3)
    print("\nTier purity on VAL (retrieved pairs only) with the current cutoffs:")
    print(summary.to_string())

    settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7, 4))
    plt.hist(cand.loc[cand["label"] == 0, "cosine"], bins=40, alpha=0.6, label="non-match")
    plt.hist(cand.loc[cand["label"] == 1, "cosine"], bins=40, alpha=0.6, label="match")
    plt.axvline(lo, linestyle="--", color="k")
    plt.axvline(hi, linestyle="--", color="k")
    plt.xlabel("SBERT cosine similarity")
    plt.ylabel("pairs")
    plt.title(f"{name}: validation score distribution")
    plt.legend()
    plt.savefig(settings.RESULTS_DIR / f"{name}_score_hist.png", dpi=150, bbox_inches="tight")
    plt.close()

    return {"threshold": t, "val_f1": f_val, "test_precision": p, "test_recall": r,
            "test_f1": f, "recall_ceiling": ceiling}


if __name__ == "__main__":
    results = {name: run(name) for name in NAMES}
    with open(settings.RESULTS_DIR / "baseline_embedding_only.json", "w") as fh:
        json.dump(results, fh, indent=2)