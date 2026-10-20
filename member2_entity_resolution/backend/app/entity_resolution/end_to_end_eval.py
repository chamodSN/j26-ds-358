"""Real end-to-end evaluation on the TEST split:
SBERT cosine + rules + cascade (Strategy B, pooled cutoffs) + real LLM on routed pairs only.

  python -m app.entity_resolution.end_to_end_eval                 # cascade only (cheap)
  python -m app.entity_resolution.end_to_end_eval --baseline      # also LLM on EVERY retrieved pair
  python -m app.entity_resolution.end_to_end_eval --with-amazon-google
"""
import argparse
import json

import numpy as np
import pandas as pd

from app.entity_resolution.datasets import load_pairs, load_records
from app.entity_resolution.llm_client import LLMClient
from app.entity_resolution.llm_matcher import judge_pair
from app.entity_resolution.router import prf
from app.entity_resolution.router_v2 import cascade_any as cascade
from app.entity_resolution.sweep_thresholds import RESULTS_DIR, load_split


def load_with_titles(name, split):
    d = load_split(name, split)
    pairs = load_pairs(name)
    pairs = pairs[pairs["split"] == split]
    records = load_records(name)
    title = dict(zip(records["record_id"], records["title"]))
    d["left"] = [title[i] for i in pairs["left_id"]]
    d["right"] = [title[i] for i in pairs["right_id"]]
    return d


def read_cutoffs(strategy="B"):
    with open(RESULTS_DIR / "chosen_thresholds_pooled.json", encoding="utf-8") as f:
        c = json.load(f)[strategy]
    return float(c["lo"]), float(c["hi"])


def ask_llm(client, d, indices, label):
    """Returns answers {idx: 0/1}, token totals and failure count."""
    answers, t_in, t_out, fails = {}, 0, 0, 0
    for n, i in enumerate(indices, 1):
        ans, res = judge_pair(client, d["left"][i], d["right"][i])
        t_in += res["input_tokens"]
        t_out += res["output_tokens"]
        if ans is None:
            fails += 1
            ans = 0
        answers[i] = ans
        if n % 25 == 0 or n == len(indices):
            print(f"  [{label}] {n}/{len(indices)} pairs judged", flush=True)
    return answers, t_in, t_out, fails


def embedding_only_f1(name, test):
    """Best single cosine threshold chosen on VAL, applied to TEST (retrieved pairs only)."""
    val = load_split(name, "val")
    best_t, best_f1 = 0.5, -1
    for t in np.arange(0.0, 1.0, 0.01):
        _, _, f1 = prf(val["y"], ((val["cos"] >= t) & (val["b"] == 1)).astype(int))
        if f1 > best_f1:
            best_t, best_f1 = t, f1
    _, _, f1 = prf(test["y"], ((test["cos"] >= best_t) & (test["b"] == 1)).astype(int))
    return float(f1)


def run_dataset(client, name, lo, hi, baseline, strategy):
    d = load_with_titles(name, "test")
    y, n_blocked = d["y"], int(d["b"].sum())
    pred, llm = cascade(d["cos"], d["v"], d["b"], lo=lo, hi=hi, strategy=strategy)
    pred, llm = np.asarray(pred, dtype=int), np.asarray(llm, dtype=bool)

    routed = np.where(llm)[0]
    answers, t_in, t_out, fails = ask_llm(client, d, routed, f"{name} cascade")
    final = pred.copy()
    for i, a in answers.items():
        final[i] = a
    p, r, f1 = prf(y, final)
    _, _, auto_f1 = prf(y, pred)

    row = dict(strategy=strategy,dataset=name, test_pairs=int(len(y)), retrieved_pairs=n_blocked,
               llm_calls=int(len(routed)), llm_rate=len(routed) / max(n_blocked, 1),
               precision=float(p), recall=float(r), f1=float(f1), auto_only_f1=float(auto_f1),
               embedding_only_f1=embedding_only_f1(name, d),
               tokens_in=t_in, tokens_out=t_out, parse_failures=fails)

    per_call = (t_in + t_out) / max(len(routed), 1)
    if baseline:
        all_idx = np.where(d["b"] == 1)[0]
        b_ans, b_in, b_out, b_fail = ask_llm(client, d, all_idx, f"{name} LLM-on-everything")
        b_pred = np.zeros(len(y), dtype=int)
        for i, a in b_ans.items():
            b_pred[i] = a
        bp, br, bf1 = prf(y, b_pred)
        row.update(baseline_precision=float(bp), baseline_recall=float(br), baseline_f1=float(bf1),
                   baseline_tokens=b_in + b_out, baseline_measured=True)
    else:
        row.update(baseline_tokens=int(per_call * n_blocked), baseline_measured=False)   # estimate
    row["token_reduction"] = 1 - (t_in + t_out) / max(row["baseline_tokens"], 1)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="also run LLM on every retrieved pair")
    ap.add_argument("--with-amazon-google", action="store_true")
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--strategy", default="B", choices=["B", "C"])
    args = ap.parse_args()

    lo, hi = read_cutoffs(args.strategy)
    client = LLMClient(max_calls=args.max_calls)
    print(f"Strategy {args.strategy}, pooled cutoffs lo={lo} hi={hi}; model={client.provider}/{client.model}")

    names = ["abt_buy", "wdc"] + (["amazon_google"] if args.with_amazon_google else [])
    rows = [run_dataset(client, n, lo, hi, args.baseline, args.strategy) for n in names]

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_DIR / f"end_to_end_results_{args.strategy}.csv", index=False)
    with open(RESULTS_DIR / f"end_to_end_results_{args.strategy}.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    cols = ["dataset", "llm_rate", "precision", "recall", "f1", "embedding_only_f1",
            "tokens_in", "tokens_out", "parse_failures", "token_reduction"]
    if args.baseline:
        cols += ["baseline_f1"]
    print("\n" + df[cols].round(3).to_string(index=False))
    if not args.baseline:
        print("\n(token_reduction is ESTIMATED from average tokens per call; run with --baseline to measure it)")
    print(f"\nNetwork calls this run: {client.network_calls}  (cache: {client.cache_path})")


if __name__ == "__main__":
    main()