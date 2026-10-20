"""Deployable (lo, hi) per strategy, chosen on pooled electronics VALIDATION data
(Abt-Buy + WDC) as: highest oracle F1 subject to an LLM budget.  Then evaluated once on each
test set (oracle F1 = perfect-LLM upper bound; real F1 comes from end_to_end_eval)."""
import argparse
import json

import numpy as np
import pandas as pd

from app.entity_resolution.sweep_thresholds import RESULTS_DIR, evaluate, load_split, sweep

POOL = ["abt_buy", "wdc"]          # electronics-only validation data
REPORT = POOL + ["amazon_google"]  # amazon_google reported for transparency only
STRATEGIES = ["B", "C"]
FRONTIER_BUDGETS = [0.15, 0.20, 0.25, 0.30, 0.40, 0.50]


def pool(parts):
    return {k: np.concatenate([p[k] for p in parts]) for k in ("y", "cos", "v", "b")}


def choose_budget(grid, budget):
    """Highest oracle F1 among configs sending <= budget of pairs to the LLM
    (ties -> fewer LLM calls). Falls back to the cheapest config if none fits."""
    ok = grid[grid["llm_rate"] <= budget]
    if ok.empty:
        return grid.sort_values("llm_rate").iloc[0]
    return ok.sort_values(["oracle_f1", "llm_rate"], ascending=[False, True]).iloc[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.30,
                    help="max share of retrieved pairs sent to the LLM (default 0.30)")
    args = ap.parse_args()

    val = pool([load_split(n, "val") for n in POOL])
    tests = {n: load_split(n, "test") for n in REPORT}
    grids = {s: sweep(val, s) for s in STRATEGIES}

    print("VALIDATION frontier: best oracle F1 within each LLM budget (pooled Abt-Buy + WDC)")
    frontier = []
    for b in FRONTIER_BUDGETS:
        row = {"budget": b}
        for s in STRATEGIES:
            r = choose_budget(grids[s], b)
            row[f"{s}_oracle_f1"] = round(float(r["oracle_f1"]), 3)
            row[f"{s}_lo/hi"] = f"{r['lo']:.2f}/{r['hi']:.2f}"
        frontier.append(row)
    print(pd.DataFrame(frontier).to_string(index=False))

    out, rows = {}, []
    for s in STRATEGIES:
        grids[s].to_csv(RESULTS_DIR / f"sweep_pooled_{s}.csv", index=False)
        row = choose_budget(grids[s], args.budget)
        lo, hi = float(row["lo"]), float(row["hi"])
        test_rows = []
        for name, d in tests.items():
            r = evaluate(d, s, lo, hi)
            r["dataset"] = name
            test_rows.append(r)
            rows.append(dict(strategy=s, lo=lo, hi=hi, dataset=name,
                             test_llm_rate=r["llm_rate"], test_oracle_f1=r["oracle_f1"]))
        out[s] = {"lo": lo, "hi": hi, "budget": args.budget,
                  "pooled_val": row.to_dict(), "test": test_rows}
        print(f"\nStrategy {s} @ budget {args.budget:.0%}: lo={lo} hi={hi}  "
              f"val llm_rate={row['llm_rate']:.3f}  val oracle F1={row['oracle_f1']:.3f}")

    with open(RESULTS_DIR / "chosen_thresholds_pooled.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n" + pd.DataFrame(rows).round(3).to_string(index=False))


if __name__ == "__main__":
    main()