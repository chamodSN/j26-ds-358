"""Did the stricter judge fix the mistakes found in round 1?   (needs NO new labelling)

  python -m app.schema_harmonization.llm_round_compare

Takes the round-1 rows you labelled (llm_decision_audit.csv) and looks up what the CURRENT judge
decided for the same pair (schema_llm_decisions.csv).  Round-1 rows are DEVELOPMENT data - the prompt
was changed after seeing them - so this shows the direction of the change, it is not the final score."""
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


def main():
    old = pd.read_csv(RESULTS_DIR / "llm_decision_audit.csv")
    old["llm_correct"] = old["llm_correct"].astype(str).str.strip().str.lower()
    old = old[(old["verdict"] == "MATCH") & old["llm_correct"].isin(["yes", "no"])]
    new = pd.read_csv(RESULTS_DIR / "schema_llm_decisions.csv").drop_duplicates(["a", "b"])
    lookup = {}
    for r in new.itertuples():
        lookup[(r.a, r.b)] = r.verdict
        lookup.setdefault((r.b, r.a), r.verdict)
    old["now"] = [lookup.get((a, b), "not asked") for a, b in zip(old["a"], old["b"])]

    wrong, right = old[old["llm_correct"] == "no"], old[old["llm_correct"] == "yes"]
    print(f"round-1 MATCH decisions that were WRONG ({len(wrong)}): what does the strict judge say now?")
    print(wrong["now"].value_counts().to_string())
    print(f"\nround-1 MATCH decisions that were RIGHT ({len(right)}): what does the strict judge say now?")
    print(right["now"].value_counts().to_string())
    still = wrong[wrong["now"] == "MATCH"]
    if len(still):
        print("\nWrong merges the strict judge STILL makes:")
        for r in still.itertuples():
            print(f"   {r.a}  <->  {r.b[:50]}")
    lost = right[right["now"] == "NON_MATCH"]
    if len(lost):
        print("\nCorrect merges the strict judge now REFUSES (recall lost):")
        for r in lost.itertuples():
            print(f"   {r.a}  <->  {r.b[:50]}")
    print("\n'not asked' = the pair no longer reaches the judge (clusters changed), so it says nothing either way.")


if __name__ == "__main__":
    main()