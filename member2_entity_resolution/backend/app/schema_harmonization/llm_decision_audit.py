"""How often is the LLM judge right?   (the number you quote at the viva)

  python -m app.schema_harmonization.llm_decision_audit --round 2            # writes llm_decision_audit_round2.csv
  ... fill the column  llm_correct  with  yes / no   (is the LLM's decision RIGHT?)
  python -m app.schema_harmonization.llm_decision_audit --round 2 --score

Round 1 = llm_decision_audit.csv (already labelled).  Later rounds NEVER re-use a pair from an earlier round,
so a round-2 score is measured on fresh decisions and not on the rows used to improve the prompt.

Why the sample is split:  a wrong MATCH silently puts values under the wrong attribute (harmful),
a wrong NON_MATCH only leaves a synonym separate (harmless fragmentation)."""
import argparse
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.schema_harmonization.attribute_inventory import load_inventory
from app.schema_harmonization.seed_schema import SEED_ATTRIBUTES

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"
DECISIONS = RESULTS_DIR / "schema_llm_decisions.csv"


def audit_path(rnd):
    return RESULTS_DIR / ("llm_decision_audit.csv" if rnd == 1 else f"llm_decision_audit_round{rnd}.csv")


def _seed_id(b):
    head = str(b).split(" (also called")[0].strip()
    return head if head in SEED_ATTRIBUTES else None


def export(rnd, n_cluster, n_non, seed):
    dec = pd.read_csv(DECISIONS).drop_duplicates(["a", "b"])
    used = set()
    for r in range(1, rnd):
        if audit_path(r).exists():
            old = pd.read_csv(audit_path(r))
            used |= set(zip(old["a"], old["b"])) | set(zip(old["b"], old["a"]))
    dec = dec[[(a, b) not in used for a, b in zip(dec["a"], dec["b"])]]
    inv = load_inventory(Path(settings.DATA_INTERIM_DIR) / "attribute_inventory.csv")
    samples = dict(zip(inv["display_name"], inv["samples"]))
    dec = dec.assign(kind=["seed" if _seed_id(b) else "cluster" for b in dec["b"]])
    parts = [dec[(dec.kind == "seed") & (dec.verdict == "MATCH")],
             dec[(dec.kind == "cluster") & (dec.verdict == "MATCH")].sample(frac=1, random_state=seed).head(n_cluster),
             dec[dec.verdict == "NON_MATCH"].sample(frac=1, random_state=seed).head(n_non)]
    out = pd.concat(parts)

    def vals_b(row):
        sid = _seed_id(row["b"])
        ex = SEED_ATTRIBUTES[sid].get("examples", []) if sid else samples.get(row["b"], [])
        return " | ".join(map(str, list(ex)[:3]))

    out["values_a"] = [" | ".join(map(str, list(samples.get(a, []))[:3])) for a in out["a"]]
    out["values_b"] = [vals_b(r) for _, r in out.iterrows()]
    out["llm_correct"] = ""
    out = out[["kind", "verdict", "a", "values_a", "b", "values_b", "llm_correct"]]
    path = audit_path(rnd)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"{len(out)} fresh decisions written to {path}  (pairs from earlier rounds excluded: {len(used) // 2})\n"
          f"  seed MATCH: {((out.kind == 'seed') & (out.verdict == 'MATCH')).sum()}"
          f"   cluster MATCH: {((out.kind == 'cluster') & (out.verdict == 'MATCH')).sum()}"
          f"   NON_MATCH: {(out.verdict == 'NON_MATCH').sum()}\n"
          "Open it in Excel. For each row decide: is the LLM's decision RIGHT?  type yes / no in 'llm_correct'.\n"
          "Judge the MEANING of the two attributes (names + values), not what you expect the system to do.")


def score(rnd):
    d = pd.read_csv(audit_path(rnd))
    d["llm_correct"] = d["llm_correct"].astype(str).str.strip().str.lower()
    d = d[d["llm_correct"].isin(["yes", "no"])]
    if d.empty:
        return print("No labelled rows yet - fill the llm_correct column first.")
    print(f"round {rnd}: {len(d)} labelled decisions\n")
    for (kind, verdict), g in d.groupby(["kind", "verdict"]):
        n_ok = int((g["llm_correct"] == "yes").sum())
        print(f"  {kind:8s} {verdict:10s} n={len(g):3d}   correct={n_ok}/{len(g)} = {n_ok / len(g):.1%}")
        for r in g[g["llm_correct"] == "no"].itertuples():
            print(f"        WRONG: {r.a}  <->  {r.b[:50]}")
    m = d[d["verdict"] == "MATCH"]
    print(f"\nWrong MATCH (harmful merge): {(m['llm_correct'] == 'no').sum()}/{len(m)}"
          "   - sample sizes are small, so quote the counts, not just the percentage")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--n-cluster", type=int, default=40)
    ap.add_argument("--n-non", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    score(a.round) if a.score else export(a.round, a.n_cluster, a.n_non, a.seed)