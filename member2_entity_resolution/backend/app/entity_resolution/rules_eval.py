from app.entity_resolution.datasets import load_pairs, load_records
from app.entity_resolution.rules import apply_rules

for name in ["abt_buy", "amazon_google", "wdc"]:
    records = load_records(name)
    pairs = load_pairs(name)
    if "blocked" not in pairs.columns:
        pairs["blocked"] = 1
    title = dict(zip(records["record_id"], records["title"]))
    val = pairs[(pairs["split"] == "val") & (pairs["blocked"] == 1)].copy()
    val["verdict"], val["reason"] = apply_rules(val, title)

    print(f"\n=== {name} (VAL, retrieved pairs: {len(val)}, matches: {int(val['label'].sum())}) ===")
    g = val.groupby("reason")["label"].agg(n="size", matches="sum")
    g["match_rate"] = (g["matches"] / g["n"]).round(3)
    print(g.to_string())
    acc, rej = val[val["verdict"] == 1], val[val["verdict"] == 0]
    if len(acc):
        print(f"ACCEPT precision: {acc['label'].mean():.3f} on {len(acc)} pairs")
    print(f"true matches wrongly REJECTED: {int(rej['label'].sum())} of {int(val['label'].sum())}")

    if name in ("abt_buy", "wdc"):
        print("\n  wrongly REJECTED true matches:")
        for _, r in rej[rej["label"] == 1].head(10).iterrows():
            print(f"    {title[r['left_id']][:110]} || {title[r['right_id']][:110]}")
        print("  wrongly ACCEPTED non-matches:")
        for _, r in acc[acc["label"] == 0].head(8).iterrows():
            print(f"    {title[r['left_id']][:110]} || {title[r['right_id']][:110]}")