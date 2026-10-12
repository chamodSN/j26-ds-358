"""
Member 4 - Evaluate ranking systems on the ESCI electronics subset (SO1).

Systems
  b1        Baseline 1: bi-encoder all-MiniLM-L6-v2, cosine(query, product) order
            (retrieval-only order, stands in for M1's dense retrieval)
  ft        fine-tuned cross-encoder (SO1), from --ft-model
  zeroshot  cross-encoder/ms-marco-MiniLM-L-6-v2 without fine-tuning (reference row)
  bm25      BM25 on product text (reference row)
  random    random order (reference row)

Run from repo root, e.g.
  python member4_reranking/src/eval_ranking.py --systems b1
  python member4_reranking/src/eval_ranking.py --systems ft --device cpu
  python member4_reranking/src/eval_ranking.py --systems b1 ft zeroshot bm25 random

Outputs (member4_reranking/results/)
  eval_<split>.json                 summary per system, per subcategory, latency,
                                    Wilcoxon p-values vs b1 (committed to git)
  per_query_<split>_<system>.csv    per-query metrics (gitignored; used for Wilcoxon)

Test split is for reporting only. Never choose settings by looking at test numbers;
use --split dev for that.
"""

import argparse
import json
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import evaluate, summarize  # noqa: E402

M4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = M4_DIR / "data" / "processed"
RESULTS_DIR = M4_DIR / "results"
BI_ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
ZERO_SHOT_CE = "cross-encoder/ms-marco-MiniLM-L-6-v2"
FT_MODEL = M4_DIR / "models" / "cross_encoder" / "best"
METRICS = ["mrr", "ndcg@10", "p@5"]


# ---------------------------------------------------------------- scorers
# Each scorer: (df) -> np.ndarray of scores, one per row.
# Each also has .score_one(query, texts) for the per-query latency measurement.

class BiEncoderScorer:
    def __init__(self, name, device, batch_size):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(name, device=device)
        self.bs = batch_size

    def _enc(self, texts):
        return self.model.encode(list(texts), batch_size=self.bs, convert_to_numpy=True,
                                 normalize_embeddings=True, show_progress_bar=False)

    def __call__(self, df):
        q = df.drop_duplicates("query_id")
        qv = dict(zip(q.query_id, self._enc(q["query"])))
        p = df.drop_duplicates("product_id")
        pv = dict(zip(p.product_id, self._enc(p["product_text"])))
        return np.array([float(qv[a] @ pv[b]) for a, b in zip(df.query_id, df.product_id)])

    def score_one(self, query, texts):
        qv = self._enc([query])[0]
        return self._enc(texts) @ qv


class CrossEncoderScorer:
    def __init__(self, name, device, batch_size, max_length=256):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(str(name), device=device, max_length=max_length)
        self.bs = batch_size

    def __call__(self, df):
        pairs = list(zip(df["query"], df["product_text"]))
        return np.asarray(self.model.predict(pairs, batch_size=self.bs, show_progress_bar=True),
                          dtype=float).reshape(-1)

    def score_one(self, query, texts):
        return self.model.predict([(query, t) for t in texts], batch_size=self.bs,
                                  show_progress_bar=False)


TOKEN_RE = re.compile(r"[a-z0-9]+")


class BM25Scorer:
    """Okapi BM25 (k1=1.5, b=0.75). IDF from the product texts in the evaluated split."""

    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b

    @staticmethod
    def tok(s):
        return TOKEN_RE.findall(str(s).lower())

    def __call__(self, df):
        prods = df.drop_duplicates("product_id")
        docs = {pid: Counter(self.tok(t)) for pid, t in zip(prods.product_id, prods.product_text)}
        n = len(docs)
        self.avgdl = np.mean([sum(c.values()) for c in docs.values()])
        dfreq = Counter(w for c in docs.values() for w in c)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in dfreq.items()}
        return np.array([self._score(self.tok(q), docs[pid])
                         for q, pid in zip(df["query"], df.product_id)])

    def _score(self, q_tokens, doc):
        dl = sum(doc.values())
        s = 0.0
        for w in q_tokens:
            tf = doc.get(w, 0)
            if tf:
                s += self.idf.get(w, 0.0) * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def score_one(self, query, texts):
        return [self._score(self.tok(query), Counter(self.tok(t))) for t in texts]


class RandomScorer:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)

    def __call__(self, df):
        return self.rng.random(len(df))

    def score_one(self, query, texts):
        return self.rng.random(len(texts))


def make_scorer(system, args):
    if system == "b1":
        return BiEncoderScorer(BI_ENCODER, args.device, args.batch_size)
    if system == "ft":
        if not Path(args.ft_model).exists():
            sys.exit(f"Fine-tuned model not found: {args.ft_model} (copy Colab 'best/' there)")
        return CrossEncoderScorer(args.ft_model, args.device, args.batch_size, args.max_length)
    if system == "zeroshot":
        return CrossEncoderScorer(ZERO_SHOT_CE, args.device, args.batch_size, args.max_length)
    if system == "bm25":
        return BM25Scorer()
    if system == "random":
        return RandomScorer(args.seed)
    raise ValueError(system)


# ---------------------------------------------------------------- helpers

def measure_latency(scorer, df, n_queries, seed):
    """Wall time to score ONE query's candidates (model already loaded)."""
    qids = df.query_id.drop_duplicates().sample(min(n_queries, df.query_id.nunique()),
                                                random_state=seed)
    groups = {q: g for q, g in df[df.query_id.isin(qids)].groupby("query_id")}
    first = next(iter(groups.values()))
    scorer.score_one(first["query"].iloc[0], list(first.product_text))  # warm-up
    times = []
    for g in groups.values():
        t0 = time.perf_counter()
        scorer.score_one(g["query"].iloc[0], list(g.product_text))
        times.append((time.perf_counter() - t0) * 1000)
    return {"queries": len(times), "mean_ms": round(float(np.mean(times)), 2),
            "p95_ms": round(float(np.percentile(times, 95)), 2),
            "avg_candidates": round(float(np.mean([len(g) for g in groups.values()])), 1)}


def wilcoxon_vs(per_query, base, other):
    a = per_query[base].set_index("query_id")
    b = per_query[other].set_index("query_id")
    common = a.index.intersection(b.index)
    out = {}
    for m in METRICS:
        d = b.loc[common, m] - a.loc[common, m]
        if np.allclose(d, 0):
            out[m] = {"mean_diff": 0.0, "p_value": 1.0}
            continue
        p = wilcoxon(b.loc[common, m], a.loc[common, m], zero_method="wilcox").pvalue
        out[m] = {"mean_diff": round(float(d.mean()), 4), "p_value": float(f"{p:.3g}"),
                  "wins": int((d > 0).sum()), "losses": int((d < 0).sum()),
                  "ties": int((d == 0).sum())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", default=["b1"],
                    choices=["b1", "ft", "zeroshot", "bm25", "random"])
    ap.add_argument("--split", default="test", choices=["dev", "test"])
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--ft-model", type=Path, default=FT_MODEL)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--latency-queries", type=int, default=100)
    ap.add_argument("--limit-queries", type=int, default=0, help="quick test on N queries")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = pd.read_parquet(args.data_dir / f"esci_elec_{args.split}.parquet")
    if args.limit_queries:
        keep = df.query_id.drop_duplicates().sample(args.limit_queries, random_state=args.seed)
        df = df[df.query_id.isin(keep)]
    print(f"{args.split}: {df.query_id.nunique():,} queries, {len(df):,} rows")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.split}{'_limit' if args.limit_queries else ''}"
    out_json = args.out_dir / f"eval_{tag}.json"
    report = json.loads(out_json.read_text()) if out_json.exists() else {"systems": {}}

    for system in args.systems:
        print(f"\n== {system} ==")
        scorer = make_scorer(system, args)
        t0 = time.perf_counter()
        scored = df.assign(score=scorer(df))
        total_s = time.perf_counter() - t0
        pq = evaluate(scored, "score", seed=args.seed)
        pq.to_csv(args.out_dir / f"per_query_{tag}_{system}.csv", index=False)
        res = summarize(pq)
        res["by_subcategory"] = {s: summarize(g) for s, g in pq.groupby("subcategory")} \
            if "subcategory" in pq else {}
        res["latency_per_query"] = measure_latency(scorer, df, args.latency_queries, args.seed)
        res["latency_per_query"]["device"] = args.device
        res["batch_scoring_seconds"] = round(total_s, 1)
        res["run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if system == "ft":
            res["model"] = str(args.ft_model)
        report["systems"][system] = res
        print(json.dumps({k: res[k] for k in ["queries", *METRICS, "latency_per_query"]}))

    # Wilcoxon (paired, per query) of every system against b1, and ft against the others
    per_query = {}
    for s in report["systems"]:
        f = args.out_dir / f"per_query_{tag}_{s}.csv"
        if f.exists():
            per_query[s] = pd.read_csv(f)
    report["wilcoxon"] = {}
    for base in ["b1", "ft"]:
        if base in per_query:
            for other in per_query:
                if other != base and f"{other}_vs_{base}" not in report["wilcoxon"] \
                        and f"{base}_vs_{other}" not in report["wilcoxon"]:
                    report["wilcoxon"][f"{other}_vs_{base}"] = wilcoxon_vs(per_query, base, other)

    report.update({"split": args.split, "data": str(args.data_dir / f"esci_elec_{args.split}.parquet"),
                   "metric_rules": "MRR/P@5: Exact only; NDCG@10 gains E1 S0.1 C0.01 I0; "
                                   "queries with >=1 Exact; random tie-break seed "
                                   f"{args.seed}"})
    out_json.write_text(json.dumps(report, indent=2))

    print("\n" + "system".ljust(10) + "".join(m.rjust(10) for m in METRICS) + "   ms/query")
    for s, r in report["systems"].items():
        print(s.ljust(10) + "".join(f"{r[m]:10.4f}" for m in METRICS)
              + f"   {r['latency_per_query']['mean_ms']:.1f}")
    for k, v in report["wilcoxon"].items():
        print(f"{k}: " + ", ".join(f"{m} diff {v[m]['mean_diff']:+.4f} p={v[m]['p_value']}"
                                   for m in METRICS))
    print(f"\nSaved {out_json}")


if __name__ == "__main__":
    main()