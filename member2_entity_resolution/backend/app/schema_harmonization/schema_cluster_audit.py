"""How strict should schema_growth be when it groups NEW attribute names?   tau_join decides.

Too low  -> different attributes get merged   (read vs write, CAS latency vs seek latency)
Too high -> synonyms stay separate            (TDP / Max TDP, hotswap / hot swap)

This script sweeps tau_join and measures both errors on a small HAND-WRITTEN pair list
(you check/edit the lists below - they are your gold judgement, not mine).

  python -m app.schema_harmonization.schema_cluster_audit
  python -m app.schema_harmonization.schema_cluster_audit --export 0.75   # clusters to label by hand
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.schema_harmonization.attribute_inventory import load_inventory
from app.schema_harmonization.attribute_matcher import AttributeMatcher
from app.schema_harmonization.schema_growth import grow_schema
from app.schema_harmonization.schema_registry import SchemaRegistry

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"

# EDIT ME: names that describe the SAME attribute and should end up in one canonical attribute
SHOULD_MERGE = [
    ("tdp", "max tdp"), ("tdp", "thermal design power"), ("hotswap", "hot swap"),
    ("number of pins", "pins"), ("number of threads", "of threads"), ("bytes sector", "bytes sec"),
    ("width", "width us"), ("depth", "depth us"), ("height", "height us"),
    ("average seek time", "seek time"), ("number of cores", "cores"),
    ("air flow", "airflow"), ("upc", "upc list"), ("ean", "ean list"),
    ("operating temp", "operating temperature"), ("release date", "official release date"),
    ("tape type", "tape format"), ("raid level", "raid"),
]
# EDIT ME: names that look alike but are DIFFERENT attributes and must stay apart
SHOULD_SEPARATE = [
    ("min operating temperature", "max operating temperature"),
    ("max operating humidity", "min operating humidity"),
    ("cas latency", "average latency"), ("processor manufacturer", "graphics controller manufacturer"),
    ("read speed", "write speed"), ("maximum read transfer rate", "maximum write transfer rate"),
    ("2 5 internal", "3 5 internal"), ("width", "height"), ("front panel", "side panel"),
    ("iometer 128k random read q 1", "iometer 128k random read q 8"),
    ("call of duty black ops gemiddelde leestijd", "call of duty black ops gemiddelde schrijftijd"),
    ("extended atx", "standard atx"), ("temperature metric operating", "temperature metric non operating"),
    ("hdmi resolution max", "dp max resolution"),
]


def assignments(df):
    """name_norm -> canonical attribute id, only for names that ended up mapped."""
    return {r.name_norm: r.attr_id for r in df.itertuples() if r.attr_id}


def pair_scores(assign):
    merged = [(a, b) for a, b in SHOULD_MERGE if a in assign and b in assign and assign[a] == assign[b]]
    wrong = [(a, b) for a, b in SHOULD_SEPARATE if a in assign and b in assign and assign[a] == assign[b]]
    return merged, wrong


def run_audit(inv, embed, tau_new, tau_known, joins, min_support=5, judge=None, lo=0.70):
    inv_names = set(inv["name_norm"])
    missing = [n for p in SHOULD_MERGE + SHOULD_SEPARATE for n in p if n not in inv_names]
    if missing:
        print("WARNING: pair names not in the inventory (ignored):", sorted(set(missing)))
    rows = []
    for tj in joins:
        # (1) min_support=1 so every NEW name lands in a cluster -> measures clustering only
        reg1 = SchemaRegistry.from_seed()
        df1, _ = grow_schema(inv, reg1, AttributeMatcher(reg1, embed, use_values=True),
                             tau_new, tau_known, min_support=1, tau_join=tj , judge=judge, tau_join_lo=lo)
        merged, wrong = pair_scores(assignments(df1))
        # (2) the real setting
        reg5 = SchemaRegistry.from_seed()
        df5, _ = grow_schema(inv, reg5, AttributeMatcher(reg5, embed, use_values=True),
                             tau_new, tau_known, min_support=min_support, tau_join=tj , judge=judge, tau_join_lo=lo)
        learned = [a for a, s in reg5.attributes.items() if s["origin"] == "learned"]
        sizes = [len(reg5.attributes[a]["aliases"]) for a in learned]
        rows.append(dict(tau_join=tj,
                         synonym_pairs_merged=f"{len(merged)}/{len(SHOULD_MERGE)}",
                         different_pairs_wrongly_merged=f"{len(wrong)}/{len(SHOULD_SEPARATE)}",
                         learned_attributes=len(learned),
                         names_promoted=int((df5['status'] == 'promoted').sum()),
                         names_low_support=int((df5['status'] == 'pending_low_support').sum()),
                         multi_name_attributes=sum(s > 1 for s in sizes),
                         largest_cluster=max(sizes) if sizes else 0,
                         _wrong=wrong, _missed=[p for p in SHOULD_MERGE if p not in merged]))
    return pd.DataFrame(rows)


def export_clusters(inv, embed, tau_new, tau_known, tau_join, min_support=5, judge=None, lo=0.70):
    reg = SchemaRegistry.from_seed()
    grow_schema(inv, reg, AttributeMatcher(reg, embed, use_values=True),
                tau_new, tau_known, min_support=min_support, tau_join=tau_join , judge=judge, tau_join_lo=lo)
    out = []
    for a, s in reg.attributes.items():
        if s["origin"] == "learned" and len(s["aliases"]) > 1:
            out.append(dict(attribute=a, support=s["support"], role=s.get("role", ""),
                            names=" || ".join(s["aliases"]), examples=" | ".join(map(str, s["examples"][:3])),
                            verdict=""))      # fill: ok / merged / not_a_spec
    path = RESULTS_DIR / f"cluster_audit_join{tau_join}.csv"
    pd.DataFrame(out).sort_values("support", ascending=False).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"{len(out)} multi-name attributes written to {path}\nFill the 'verdict' column: ok / merged / not_a_spec")


def main():
    from app.schema_harmonization.text_embedder import embed_texts
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", type=float, default=None, help="write multi-name clusters of this tau_join to CSV")
    ap.add_argument("--llm", action="store_true", help="3-tier: LLM judges the middle band (lo <= sim < tau_join)")
    ap.add_argument("--join", type=float, default=0.85, help="auto-merge level used with --llm")
    ap.add_argument("--lo", type=float, default=0.70, help="below this: never merged (with --llm)")
    args = ap.parse_args()
    inv = load_inventory(Path(settings.DATA_INTERIM_DIR) / "attribute_inventory.csv")
    thr = json.loads((RESULTS_DIR / "schema_thresholds.json").read_text(encoding="utf-8"))
    judge = None
    if args.llm:
        from app.entity_resolution.llm_client import LLMClient
        from app.schema_harmonization.schema_llm_judge import LLMAttributeJudge
        judge = LLMAttributeJudge(LLMClient())
    if args.export is not None:
        export_clusters(inv, embed_texts, thr["tau_new"], thr["tau_known"], args.export, judge=judge, lo=args.lo)
    else:
        joins = [args.join] if args.llm else [0.70, 0.75, 0.80, 0.85, 0.90]
        res = run_audit(inv, embed_texts, thr["tau_new"], thr["tau_known"], joins, judge=judge, lo=args.lo)
        show = res.drop(columns=["_wrong", "_missed"])
        print("\n" + show.to_string(index=False))
        for r in res.itertuples():
            print(f"\ntau_join={r.tau_join}\n  wrongly merged: {r._wrong}\n  synonyms still apart: {r._missed}")
        show.to_csv(RESULTS_DIR / ("cluster_audit_llm.csv" if args.llm else "cluster_audit_sweep.csv"), index=False)

        if judge is not None:
         print("\nLLM judge:", dict(judge.stats))
        path = RESULTS_DIR / "schema_llm_decisions.csv"
        pd.DataFrame(judge.log).drop_duplicates(["a", "b"]).to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Every LLM decision written to {path}  (read it - this is your audit trail)")

if __name__ == "__main__":
    main()