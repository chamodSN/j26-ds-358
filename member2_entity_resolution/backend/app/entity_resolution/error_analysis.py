from app.entity_resolution.baseline_eval import cosine_for_pairs
from app.entity_resolution.datasets import load_pairs, load_records
from app.entity_resolution.embeddings import embed_records_cached

NAME = "abt_buy"   # then try "amazon_google"

records = load_records(NAME)
emb = embed_records_cached(records, NAME)
pairs = load_pairs(NAME)
pairs["cosine"] = cosine_for_pairs(pairs, records, emb)

title = dict(zip(records["record_id"], records["title"]))
val = pairs[(pairs["split"] == "val") & (pairs["blocked"] == 1)].copy()
val["lt"] = val["left_id"].map(title)
val["rt"] = val["right_id"].map(title)


def show(df, header, n=10):
    print("\n" + header)
    for _, r in df.head(n).iterrows():
        print(f"  {r['cosine']:.3f} | {r['lt'][:58]} || {r['rt'][:58]}")


show(val[val["label"] == 1].sort_values("cosine"),
     "TRUE matches with the LOWEST scores (the low tier would lose these):")
show(val[val["label"] == 0].sort_values("cosine", ascending=False),
     "NON-matches with the HIGHEST scores (look-alikes that fool the embedding):")