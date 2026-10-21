"""Evaluate attribute -> canonical-schema decisions against YOUR hand labels.
Thresholds are chosen on a DEV half; the TEST half is evaluated once.
Also an ablation: embed 'name + sample values' (our design) vs 'name only'.

  python -m app.schema_harmonization.schema_eval

Needs data/interim/schema_gold.csv = schema_gold_template.csv with the 'gold' column filled:
    <seed attribute id>   the attribute means the same as that canonical attribute
    NEW:<snake_name>      a real attribute the seed schema does not cover
    NOISE                 junk / not a product attribute
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import settings
from app.schema_harmonization.attribute_inventory import SAMPLE_SEP
from app.schema_harmonization.attribute_matcher import AMBIGUOUS, KNOWN, NEW, AttributeMatcher, classify
from app.schema_harmonization.schema_registry import SchemaRegistry

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"
REVIEW_BUDGET = 0.25      # at most 25% of attributes may be sent to the review queue
TAU_NEW_GRID = np.round(np.arange(0.30, 0.85, 0.05), 2)


def load_gold(path, valid_ids):
    g = pd.read_csv(path, keep_default_na=False)
    g = g[g["gold"].astype(str).str.strip() != ""].copy()
    g["gold"] = g["gold"].astype(str).str.strip()
    g["samples"] = g["samples"].apply(lambda s: [x for x in str(s).split(SAMPLE_SEP) if x])

    def kind(label):
        if label in valid_ids:
            return "known"
        if label.upper().startswith("NEW:"):
            return "new"
        if label.upper() == "NOISE":
            return "noise"
        raise ValueError(f"Unknown label '{label}'. Use a seed id {sorted(valid_ids)}, NEW:<name> or NOISE.")

    g["gold_kind"] = g["gold"].apply(kind)
    return g.reset_index(drop=True)


def metrics(best_id, best_sim, gold_kind, gold, tau_new, tau_known):
    kind = np.array([classify(s, tau_new, tau_known) for s in best_sim])
    keep = gold_kind != "noise"
    k, bi, gk, gi = kind[keep], best_id[keep], gold_kind[keep], gold[keep]
    correct = ((gk == "known") & (k == KNOWN) & (bi == gi)) | ((gk == "new") & (k == NEW))
    decided = k != AMBIGUOUS

    def mean(x):
        return float(x.mean()) if len(x) else float("nan")

    noise = ~keep
    return dict(n=int(keep.sum()), strict_acc=mean(correct), ambiguous_rate=mean(~decided),
                acc_decided=mean(correct[decided]), known_acc=mean(correct[gk == "known"]),
                new_recall=mean(correct[gk == "new"]),
                noise_wrongly_known=mean(kind[noise] == KNOWN) if noise.any() else float("nan"))


def sweep(best_id, best_sim, gold_kind, gold):
    rows = []
    for tn in TAU_NEW_GRID:
        for tk in np.round(np.arange(tn + 0.05, 0.96, 0.05), 2):
            rows.append(dict(tau_new=float(tn), tau_known=float(tk),
                             **metrics(best_id, best_sim, gold_kind, gold, tn, tk)))
    return pd.DataFrame(rows)


def choose(grid, budget=REVIEW_BUDGET):
    ok = grid[grid["ambiguous_rate"] <= budget]
    if ok.empty:
        return grid.sort_values("strict_acc", ascending=False).iloc[0]
    return ok.sort_values(["acc_decided", "ambiguous_rate"], ascending=[False, True]).iloc[0]


def run_eval(gold, embed_fn, seed=42):
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(gold))
    dev, test = gold.iloc[order[: len(gold) // 2]], gold.iloc[order[len(gold) // 2:]]
    rows, chosen = [], {}
    for variant, use_values in (("name + sample values", True), ("name only", False)):
        matcher = AttributeMatcher(SchemaRegistry.from_seed(), embed_fn, use_values=use_values)
        scored = {}
        for part, df in (("dev", dev), ("test", test)):
            bid, bsim, _ = matcher.score(list(df["display_name"]), list(df["samples"]))
            scored[part] = (bid, bsim, df["gold_kind"].to_numpy(), df["gold"].to_numpy())
        best = choose(sweep(*scored["dev"]))
        tn, tk = float(best["tau_new"]), float(best["tau_known"])
        m = metrics(*scored["test"][:2], scored["test"][2], scored["test"][3], tn, tk)
        rows.append(dict(variant=variant, tau_new=tn, tau_known=tk,
                         dev_acc_decided=float(best["acc_decided"]), dev_ambiguous=float(best["ambiguous_rate"]),
                         **{f"test_{k}": v for k, v in m.items()}))
        if use_values:
            chosen = dict(tau_new=tn, tau_known=tk, review_budget=REVIEW_BUDGET, n_dev=len(dev), n_test=len(test))
    return pd.DataFrame(rows), chosen


def main():
    from app.schema_harmonization.text_embedder import embed_texts
    path = Path(settings.DATA_INTERIM_DIR) / "schema_gold.csv"
    if not path.exists():
        raise SystemExit(f"Missing {path}. Fill the 'gold' column of schema_gold_template.csv and save it as schema_gold.csv.")
    gold = load_gold(path, set(SchemaRegistry.from_seed().attributes))
    print(f"Labelled attributes: {len(gold)}   (known {int((gold.gold_kind == 'known').sum())}, "
          f"new {int((gold.gold_kind == 'new').sum())}, noise {int((gold.gold_kind == 'noise').sum())})")
    table, chosen = run_eval(gold, embed_texts)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(RESULTS_DIR / "schema_eval_results.csv", index=False)
    (RESULTS_DIR / "schema_thresholds.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    pd.set_option("display.width", 200)
    print("\n" + table.round(3).T.to_string(header=False))
    print(f"\nSaved schema_eval_results.csv and schema_thresholds.json in {RESULTS_DIR}")


if __name__ == "__main__":
    main()