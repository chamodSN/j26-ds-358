"""Human review of the schema proposals (the review queue of the design).

The LLM never changes the schema by itself. It SUGGESTS:
   alias : 'this ambiguous name is another name for canonical attribute X'
   merge : 'this name belongs with that other name'
You open research/results/schema_review.csv, type  accept / reject  in the `decision` column, run schema_demo
again, and every accepted suggestion is applied (and logged). Earlier decisions are never overwritten."""
from pathlib import Path

import pandas as pd

from app.schema_harmonization.seed_schema import SEED_ATTRIBUTES

REVIEW_PATH = Path(__file__).resolve().parents[3] / "research" / "results" / "schema_review.csv"
KEY = ["kind", "name"]
COLS = ["kind", "name", "display_name", "listings", "values", "suggested_target", "target_label",
        "target_values", "decision"]


def export_review(df, inventory, path=REVIEW_PATH, top=40):
    """Write the top-`top` LLM suggestions (by number of listings affected). Keeps old decisions."""
    sug = df[df["suggest_kind"] != ""].sort_values("count", ascending=False).head(top)
    samples = dict(zip(inventory["name_norm"], inventory["samples"]))
    display = dict(zip(inventory["name_norm"], inventory["display_name"]))
    rows = []
    for r in sug.itertuples():
        if r.suggest_kind == "alias":
            target_txt = r.suggest_target
            target_vals = SEED_ATTRIBUTES.get(r.suggest_target, {}).get("examples", [])
        else:
            target_txt = display.get(r.suggest_target, r.suggest_target)
            target_vals = samples.get(r.suggest_target, [])
        rows.append(dict(kind=r.suggest_kind, name=r.name_norm, display_name=r.display_name, listings=int(r.count),
                         values=" | ".join(map(str, list(samples.get(r.name_norm, []))[:3])),
                         suggested_target=r.suggest_target, target_label=target_txt,
                         target_values=" | ".join(map(str, list(target_vals)[:3])), decision=""))
    new = pd.DataFrame(rows, columns=COLS)
    path = Path(path)
    if path.exists():
        old = pd.read_csv(path).fillna("")
        decided = {(k, n): d for k, n, d in zip(old["kind"], old["name"], old["decision"])}
        new["decision"] = [decided.get((k, n), "") for k, n in zip(new["kind"], new["name"])]
        keep = old[~old.set_index(KEY).index.isin(new.set_index(KEY).index) & (old["decision"] != "")]
        new = pd.concat([new, keep], ignore_index=True)       # decisions on names that dropped out stay recorded
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(path, index=False, encoding="utf-8-sig")
    return len(new), int((new["decision"] == "").sum())


def load_hints(path=REVIEW_PATH):
    """-> {'alias': {name_norm: attr_id}, 'merge': {name_norm: partner_name_norm}} from accepted rows."""
    path = Path(path)
    if not path.exists():
        return {}
    d = pd.read_csv(path).fillna("")
    d["decision"] = d["decision"].astype(str).str.strip().str.lower()
    acc = d[d["decision"] == "accept"]
    return {"alias": {r.name: r.suggested_target for r in acc.itertuples() if r.kind == "alias"},
            "merge": {r.name: r.suggested_target for r in acc.itertuples() if r.kind == "merge"}}