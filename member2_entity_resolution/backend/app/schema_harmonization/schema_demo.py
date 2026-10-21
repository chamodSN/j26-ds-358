"""Grow the canonical schema from the real WDC attributes and show what happened.

  python -m app.schema_harmonization.schema_demo
Reads thresholds chosen by schema_eval (research/results/schema_thresholds.json)."""
import argparse
import json
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.entity_resolution.datasets import load_records
from app.schema_harmonization.attribute_inventory import KVP_COLUMN, load_inventory
from app.schema_harmonization.attribute_matcher import AttributeMatcher
from app.schema_harmonization.schema_growth import coverage, grow_schema, harmonize_record
from app.schema_harmonization.schema_registry import SchemaRegistry
from app.schema_harmonization.text_embedder import embed_texts
from app.schema_harmonization.schema_review import REVIEW_PATH, export_review, load_hints

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"
MIN_SUPPORT = 5

def print_llm_report(df, judge):
    print("\nLLM judge:", dict(judge.stats))
    for reason, text in [("llm_suggests_alias", "ambiguous names the LLM SUGGESTS are aliases of a seed attribute (-> review queue)"),
                           ("llm_not_seed", "ambiguous names the LLM says are NOT the nearest seed attribute (treated as NEW)"),
                           ("llm_suggests_merge", "names the LLM SUGGESTS merging with a candidate (-> review queue)"),
                           ("llm_separate", "names the LLM kept apart from the nearest candidate"),
                           ("review_accept", "names placed by a decision YOU accepted in schema_review.csv")]:
        sub = df[df["reason"] == reason].sort_values("count", ascending=False)
        print(f"\n{len(sub):4d} {text}")
        for r in sub.head(10).itertuples():
            print(f"      {r.count:4d}  {r.display_name:34s} nearest={r.nearest}  sim={r.sim}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="3-tier schema growth: the LLM judges the middle band")
    args = ap.parse_args()
    inv = load_inventory(Path(settings.DATA_INTERIM_DIR) / "attribute_inventory.csv")
    thr_path = RESULTS_DIR / "schema_thresholds.json"
    if thr_path.exists():
        thr = json.loads(thr_path.read_text(encoding="utf-8"))
        tau_new, tau_known = thr["tau_new"], thr["tau_known"]
        print(f"Thresholds from schema_eval (chosen on labelled dev set): tau_new={tau_new} tau_known={tau_known}")
    else:
        tau_new, tau_known = 0.45, 0.70
        print("WARNING: schema_thresholds.json missing - using PLACEHOLDER thresholds 0.45 / 0.70 (run schema_eval first)")

    reg = SchemaRegistry.from_seed()
    matcher = AttributeMatcher(reg, embed_texts, use_values=True)
    judge = None
    if args.llm:
        from app.entity_resolution.llm_client import LLMClient
        from app.schema_harmonization.schema_llm_judge import LLMAttributeJudge
        judge = LLMAttributeJudge(LLMClient())
        hints = load_hints()                       # decisions you accepted in schema_review.csv (empty on the first run)
    df, mapping = grow_schema(inv, reg, matcher, tau_new, tau_known, MIN_SUPPORT, judge=judge,
                                judge_mode="suggest", hints=hints)     # judge: tau_join 0.85, lo 0.70; LLM only SUGGESTS
    print(f"Review decisions applied: {sum(len(v) for v in hints.values())}")

    print(f"\nAttribute names: {len(df)}   min_support for promotion: {MIN_SUPPORT} records")
    print(df["status"].value_counts().to_string())
    
    if judge is not None:
          print_llm_report(df, judge)
          total, todo = export_review(df, inv)
          print(f"\nReview queue written to {REVIEW_PATH}\n  {total} rows, {todo} still need a decision (accept / reject)")

    print(f"\nSchema version: 1 -> {reg.version}   canonical attributes: "
          f"{len([a for a in reg.attributes.values() if a['origin'] == 'seed'])} seed + "
          f"{len([a for a in reg.attributes.values() if a['origin'] == 'learned'])} learned")
    print("\nNEW attributes added to the schema:")
    for a, spec in reg.attributes.items():
        if spec["origin"] == "learned":
            print(f"  + {a:24s} support={spec['support']:4d}  names={spec['aliases'][:4]}  e.g. {spec['examples'][:2]}")

    queue = df[df["status"] == "review_queue"].sort_values("count", ascending=False).head(12)
    print("\nReview queue (ambiguous, NOT added automatically) - top 12:")
    for r in queue.itertuples():
        print(f"  {r.count:4d}  {r.display_name:28s} nearest={r.nearest} sim={r.sim}")

    records = load_records("wdc")
    seed_map = SchemaRegistry.from_seed().alias_index()      # the seed schema alone, before any growth or review decision
    before, after = coverage(records[KVP_COLUMN], seed_map), coverage(records[KVP_COLUMN], mapping)
    print("\nBackfill (listings re-mapped to the grown schema):")
    print(f"  mean canonical attributes per listing: {before['mean_canonical_per_listing']:.2f} -> {after['mean_canonical_per_listing']:.2f}")
    print(f"  share of listings with >=1 canonical attribute: {before['share_with_canonical']:.1%} -> {after['share_with_canonical']:.1%}")

    learned = {a for a, s in reg.attributes.items() if s["origin"] == "learned"}
    shown = 0
    print("\nExample listings using a learned attribute:")
    for raw in records[KVP_COLUMN]:
        out = harmonize_record(raw, mapping)
        if learned & set(out["canonical"]) and shown < 3:
            print("  ", json.dumps(out["canonical"], ensure_ascii=False)[:160])
            shown += 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(RESULTS_DIR / "schema_growth_report.csv", index=False)
    reg.save(Path(settings.CANONICAL_SCHEMA_PATH))
    print(f"\nSaved schema -> {settings.CANONICAL_SCHEMA_PATH}\nSaved report -> {RESULTS_DIR / 'schema_growth_report.csv'}")


if __name__ == "__main__":
    main()