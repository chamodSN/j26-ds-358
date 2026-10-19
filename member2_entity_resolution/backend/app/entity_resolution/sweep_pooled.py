"""One deployable (lo, hi) chosen on pooled electronics validation data
(Abt-Buy + WDC), then evaluated once on each test set."""
import json

import numpy as np
import pandas as pd

from app.entity_resolution.sweep_thresholds import (
    RESULTS_DIR, choose, evaluate, load_split, sweep,
)

POOL = ["abt_buy", "wdc"]          # electronics-only validation data
REPORT = POOL + ["amazon_google"]  # amazon_google reported for transparency only


def pool(parts):
    return {k: np.concatenate([p[k] for p in parts]) for k in ("y", "cos", "v", "b")}


def main():
    val = pool([load_split(n, "val") for n in POOL])
    grid = sweep(val, "B")
    row, best = choose(grid)
    lo, hi = float(row["lo"]), float(row["hi"])

    rows = []
    for name in REPORT:
        r = evaluate(load_split(name, "test"), "B", lo, hi)
        r["dataset"] = name
        rows.append(r)

    out = {"lo": lo, "hi": hi, "val_best_oracle_f1": best,
           "pooled_val": row.to_dict(), "test": rows}
    with open(RESULTS_DIR / "chosen_thresholds_pooled.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Pooled electronics cutoff (Strategy B): lo={lo}  hi={hi}  "
          f"(val llm_rate={row['llm_rate']:.3f}, val oracle F1={row['oracle_f1']:.3f})\n")
    print(pd.DataFrame(rows)[["dataset", "llm_rate", "auto_f1", "oracle_f1"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()