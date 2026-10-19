
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.entity_resolution.datasets import load_pairs, load_records
from app.entity_resolution.embeddings import embed_records_cached
from app.entity_resolution.router import cascade, prf
from app.entity_resolution.rules import apply_rules


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[3]
RESULTS_DIR = ROOT_DIR / "research" / "results"

DATASETS = ["abt_buy", "amazon_google", "wdc"]

# Initial proposal thresholds (not yet optimized)
LOW = 0.65
HIGH = 0.90


# --------------------------------------------------
# Calculate cosine similarity using cached embeddings
# --------------------------------------------------

def calculate_cosine(name, records, pairs):
    """
    Calculate cosine similarity for product pairs.

    Uses existing cached SBERT embeddings.
    Embeddings are already L2-normalized.
    """

    embeddings = embed_records_cached(records, name)

    id_to_index = {
        record_id: i
        for i, record_id in enumerate(records["record_id"])
    }

    left_indices = [
        id_to_index[record_id]
        for record_id in pairs["left_id"]
    ]

    right_indices = [
        id_to_index[record_id]
        for record_id in pairs["right_id"]
    ]

    cosine = np.sum(
        embeddings[left_indices] * embeddings[right_indices],
        axis=1,
    )

    return np.asarray(cosine, dtype=float)


# --------------------------------------------------
# Evaluate a routing strategy
# --------------------------------------------------

def evaluate_strategy(
    y,
    cosine,
    verdicts,
    blocked,
    strategy,
    lo,
    hi,
):
    """
    Evaluate the cascade router.

    Automatic F1:
        Routed pairs are temporarily treated as non-matches.

    Oracle F1:
        Assumes a perfect LLM correctly classifies every
        routed pair. This is a theoretical upper bound.
    """

    pred, llm_mask = cascade(
        cosine,
        verdicts,
        blocked,
        lo=lo,
        hi=hi,
        strategy=strategy,
    )

    # Automatic-only predictions
    auto_precision, auto_recall, auto_f1 = prf(y, pred)

    # Perfect-LLM upper bound
    oracle_pred = pred.copy()
    oracle_pred[llm_mask] = y[llm_mask]

    oracle_precision, oracle_recall, oracle_f1 = prf(
        y,
        oracle_pred,
    )

    # Evaluate only automatically decided pairs
    decided_mask = ~llm_mask

    decided_precision, decided_recall, decided_f1 = prf(
        y[decided_mask],
        pred[decided_mask],
    )

    return {
        "strategy": strategy,
        "low_threshold": float(lo),
        "high_threshold": float(hi),
        "total_pairs": int(len(y)),
        "llm_pairs": int(llm_mask.sum()),
        "llm_rate": float(llm_mask.mean()),
        "automatic_pairs": int(decided_mask.sum()),
        "auto_precision": float(auto_precision),
        "auto_recall": float(auto_recall),
        "auto_f1": float(auto_f1),
        "decided_precision": float(decided_precision),
        "decided_recall": float(decided_recall),
        "decided_f1": float(decided_f1),
        "oracle_precision": float(oracle_precision),
        "oracle_recall": float(oracle_recall),
        "oracle_f1": float(oracle_f1),
        "routed_true_matches": int(
            (llm_mask & (y == 1)).sum()
        ),
        "missed_true_matches": int(
            ((pred == 0) & ~llm_mask & (y == 1)).sum()
        ),
    }


# --------------------------------------------------
# Main evaluation
# --------------------------------------------------

def main():

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results = []

    for name in DATASETS:

        print("\n" + "=" * 60)
        print(f"DATASET: {name}")
        print("=" * 60)

        # Load dataset
        pairs = load_pairs(name)

        # Validation split only
        pairs = pairs[
            pairs["split"] == "val"
        ].copy()

        records = load_records(name)

        # Map record IDs to product titles
        title_map = dict(
            zip(
                records["record_id"],
                records["title"],
            )
        )

        # SBERT cosine similarity
        cosine = calculate_cosine(
            name,
            records,
            pairs,
        )

        # Rule-based decisions
        verdicts, reasons = apply_rules(
            pairs,
            title_map,
        )

        verdicts = np.asarray(
            verdicts,
            dtype=int,
        )

        # Ground-truth labels
        y = pairs["label"].to_numpy(
            dtype=int
        )

        # WDC has supplied labeled pairs rather than
        # evaluated FAISS blocking candidates.
        if "blocked" in pairs.columns:
            blocked = pairs["blocked"].to_numpy(
                dtype=int
            )
        else:
            blocked = np.ones(
                len(pairs),
                dtype=int,
            )

        print(f"Validation pairs: {len(y)}")
        print(f"Positive matches: {int(y.sum())}")

        # Compare Strategy A and Strategy B
        for strategy in ["A", "B"]:

            result = evaluate_strategy(
                y=y,
                cosine=cosine,
                verdicts=verdicts,
                blocked=blocked,
                strategy=strategy,
                lo=LOW,
                hi=HIGH,
            )

            result["dataset"] = name
            all_results.append(result)

            print(f"\nStrategy {strategy}")

            print(
                f"  LLM routing: "
                f"{result['llm_pairs']}/{len(y)} "
                f"({result['llm_rate']:.1%})"
            )

            print(
                f"  Automatic-only F1: "
                f"{result['auto_f1']:.3f}"
            )

            print(
                f"  Oracle F1 (perfect LLM): "
                f"{result['oracle_f1']:.3f}"
            )

            print(
                f"  True matches missed without LLM: "
                f"{result['missed_true_matches']}"
            )

    # --------------------------------------------------
    # Save results
    # --------------------------------------------------

    summary = pd.DataFrame(
        all_results
    )

    output_csv = (
        RESULTS_DIR / "router_comparison.csv"
    )

    output_json = (
        RESULTS_DIR / "router_comparison.json"
    )

    summary.to_csv(
        output_csv,
        index=False,
    )

    with open(
        output_json,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            all_results,
            file,
            indent=2,
        )

    # --------------------------------------------------
    # Display summary
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("ROUTER COMPARISON SUMMARY")
    print("=" * 60)

    print(
        summary[
            [
                "dataset",
                "strategy",
                "llm_rate",
                "auto_precision",
                "auto_recall",
                "auto_f1",
                "oracle_f1",
            ]
        ].to_string(
            index=False
        )
    )

    print(f"\nSaved: {output_csv}")
    print(f"Saved: {output_json}")


if __name__ == "__main__":
    main()
