"""Choose the lo/hi cosine cut-offs for the 3-tier cascade from DATA (validation only),
then evaluate the chosen cut-offs ONCE on the test split."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.entity_resolution.datasets import load_pairs, load_records
from app.entity_resolution.router import prf
from app.entity_resolution.router_v2 import cascade_any as cascade
from app.entity_resolution.router_eval import calculate_cosine
from app.entity_resolution.rules import apply_rules

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"
DATASETS = ["abt_buy", "amazon_google", "wdc"]
STRATEGIES = ["A", "B"]
LO_GRID = np.round(np.arange(0.20, 0.90, 0.02), 2)
HI_GRID = np.round(np.arange(0.30, 1.00, 0.02), 2)
TOLERANCE = 0.01   # accept any config within 1 F1 point of the best oracle F1 on VAL


def load_split(name, split):
    pairs = load_pairs(name)
    pairs = pairs[pairs["split"] == split].copy()
    records = load_records(name)
    title_map = dict(zip(records["record_id"], records["title"]))
    cosine = calculate_cosine(name, records, pairs)
    verdicts = np.asarray(apply_rules(pairs, title_map)[0], dtype=int)
    y = pairs["label"].to_numpy(dtype=int)
    blocked = (pairs["blocked"].to_numpy(dtype=int) if "blocked" in pairs.columns
               else np.ones(len(pairs), dtype=int))
    return dict(y=y, cos=cosine, v=verdicts, b=blocked)


def evaluate(d, strategy, lo, hi):
    pred, llm = cascade(d["cos"], d["v"], d["b"], lo=lo, hi=hi, strategy=strategy)
    pred, llm = np.asarray(pred, dtype=int), np.asarray(llm, dtype=bool)
    oracle = pred.copy()
    oracle[llm] = d["y"][llm]
    _, _, auto_f1 = prf(d["y"], pred)
    p, r, oracle_f1 = prf(d["y"], oracle)
    n_blocked = max(int(d["b"].sum()), 1)
    return dict(strategy=strategy, lo=float(lo), hi=float(hi),
                llm_calls=int(llm.sum()),
                llm_rate=float(llm.sum() / n_blocked),   # share of retrieved candidates sent to the LLM
                auto_f1=float(auto_f1), oracle_precision=float(p),
                oracle_recall=float(r), oracle_f1=float(oracle_f1))


def sweep(d, strategy):
    rows = [evaluate(d, strategy, lo, hi)
            for lo in LO_GRID for hi in HI_GRID if hi > lo + 0.02]
    return pd.DataFrame(rows)


def choose(grid):
    """Cheapest config whose oracle F1 is within TOLERANCE of the best on validation."""
    best = grid["oracle_f1"].max()
    ok = grid[grid["oracle_f1"] >= best - TOLERANCE]
    row = ok.sort_values(["llm_rate", "oracle_f1"], ascending=[True, False]).iloc[0]
    return row, float(best)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    chosen, summary = {}, []
    fig, axes = plt.subplots(1, len(DATASETS), figsize=(15, 4.2), sharey=False)

    for ax, name in zip(axes, DATASETS):
        val, test = load_split(name, "val"), load_split(name, "test")
        chosen[name] = {}
        for strategy in STRATEGIES:
            grid = sweep(val, strategy)
            grid.to_csv(RESULTS_DIR / f"sweep_{name}_{strategy}.csv", index=False)
            row, best = choose(grid)
            t = evaluate(test, strategy, row["lo"], row["hi"])      # evaluated once
            chosen[name][strategy] = dict(
                lo=row["lo"], hi=row["hi"], val_best_oracle_f1=best,
                val=row.to_dict(), test=t)
            summary.append(dict(dataset=name, strategy=strategy, lo=row["lo"], hi=row["hi"],
                                val_llm_rate=row["llm_rate"], val_oracle_f1=row["oracle_f1"],
                                test_llm_rate=t["llm_rate"], test_oracle_f1=t["oracle_f1"],
                                test_auto_f1=t["auto_f1"]))
            front = grid.sort_values("llm_rate").assign(best=lambda g: g["oracle_f1"].cummax())
            ax.plot(front["llm_rate"] * 100, front["best"], label=f"Strategy {strategy}")
            ax.scatter([row["llm_rate"] * 100], [row["oracle_f1"]], zorder=3)
        ax.set_title(name)
        ax.set_xlabel("% of candidates sent to LLM")
        ax.set_ylabel("oracle F1 (validation)")
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "sweep_frontier.png", dpi=150)

    with open(RESULTS_DIR / "chosen_thresholds.json", "w", encoding="utf-8") as f:
        json.dump(chosen, f, indent=2)
    out = pd.DataFrame(summary)
    out.to_csv(RESULTS_DIR / "sweep_summary.csv", index=False)
    print(out.round(3).to_string(index=False))
    print(f"\nSaved sweep CSVs, sweep_frontier.png, chosen_thresholds.json in {RESULTS_DIR}")


if __name__ == "__main__":
    main()