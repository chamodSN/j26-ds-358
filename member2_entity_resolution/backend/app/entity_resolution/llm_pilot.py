"""Small, cheap pilot: 40 VALIDATION pairs the cascade would send to the LLM.
Checks the API works, the answers parse, accuracy is sane, and projects the full-run cost."""
import numpy as np

from app.entity_resolution.end_to_end_eval import load_with_titles, read_cutoffs
from app.entity_resolution.llm_client import LLMClient
from app.entity_resolution.llm_matcher import judge_pair
from app.entity_resolution.router import cascade

N_PILOT = 40


def main():
    lo, hi = read_cutoffs()
    client = LLMClient(max_calls=N_PILOT + 10)
    rng = np.random.default_rng(42)
    rows = []
    for name in ["abt_buy", "wdc"]:
        d = load_with_titles(name, "val")
        _, llm = cascade(d["cos"], d["v"], d["b"], lo=lo, hi=hi, strategy="B")
        idx = np.where(np.asarray(llm, dtype=bool))[0]
        pick = rng.choice(idx, size=min(N_PILOT // 2, len(idx)), replace=False)
        for i in pick:
            ans, res = judge_pair(client, d["left"][i], d["right"][i])
            rows.append((name, int(d["y"][i]), ans, res["input_tokens"], res["output_tokens"],
                         d["left"][i][:55], d["right"][i][:55]))

    ok = [r for r in rows if r[2] is not None]
    acc = sum(r[1] == r[2] for r in ok) / max(len(ok), 1)
    t_in = sum(r[3] for r in rows) / len(rows)
    t_out = sum(r[4] for r in rows) / len(rows)
    print(f"Pairs judged: {len(rows)}   unparseable: {len(rows) - len(ok)}")
    print(f"Accuracy on routed pairs: {acc:.3f}   (positives in sample: {sum(r[1] for r in rows)})")
    print(f"Avg tokens per call: in={t_in:.0f}  out={t_out:.1f}")
    print(f"Projected full cascade run (~460 calls): in={t_in * 460:,.0f}  out={t_out * 460:,.0f} tokens")
    print("\nWrong answers:")
    for r in rows:
        if r[2] != r[1]:
            print(f"  true={r[1]} llm={r[2]} | {r[5]} || {r[6]}")


if __name__ == "__main__":
    main()