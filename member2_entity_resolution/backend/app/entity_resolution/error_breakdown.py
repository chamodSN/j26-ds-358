"""Where does the cascade lose F1 versus LLM-on-everything?
Uses cached LLM answers only (no new calls, no cost)."""
import numpy as np
import pandas as pd

from app.entity_resolution.end_to_end_eval import load_with_titles, read_cutoffs
from app.entity_resolution.llm_client import LLMClient
from app.entity_resolution.llm_matcher import judge_pair
from app.entity_resolution.router import cascade

RULE = {1: "ACCEPT", 0: "REJECT", -1: "UNDECIDED"}


def band(c, lo, hi):
    return "cos>=hi" if c >= hi else ("cos mid" if c >= lo else "cos<lo")


def main():
    lo, hi = read_cutoffs()
    client = LLMClient(max_calls=0)          # cache only
    for name in ["abt_buy", "wdc"]:
        d = load_with_titles(name, "test")
        y = d["y"]
        pred, llm = cascade(d["cos"], d["v"], d["b"], lo=lo, hi=hi, strategy="B")
        final = np.asarray(pred, dtype=int).copy()
        llm = np.asarray(llm, dtype=bool)
        all_llm = np.zeros(len(y), dtype=int)

        for i in np.where(d["b"] == 1)[0]:
            ans, _ = judge_pair(client, d["left"][i], d["right"][i])
            all_llm[i] = ans or 0
            if llm[i]:
                final[i] = ans or 0

        group = []
        for i in range(len(y)):
            if d["b"][i] == 0:
                group.append("not retrieved by blocking")
            else:
                group.append(f"{band(d['cos'][i], lo, hi)} | rule {RULE[d['v'][i]]} | "
                             + ("LLM" if llm[i] else "auto"))
        df = pd.DataFrame(dict(group=group, y=y, final=final, all_llm=all_llm))
        df["casc_FN"] = ((df.y == 1) & (df.final == 0)).astype(int)
        df["casc_FP"] = ((df.y == 0) & (df.final == 1)).astype(int)
        df["llm_FN"] = ((df.y == 1) & (df.all_llm == 0)).astype(int)
        df["llm_FP"] = ((df.y == 0) & (df.all_llm == 1)).astype(int)
        df["positives"] = df.y

        t = df.groupby("group").agg(n=("y", "size"), positives=("positives", "sum"),
                                    casc_FN=("casc_FN", "sum"), casc_FP=("casc_FP", "sum"),
                                    llm_FN=("llm_FN", "sum"), llm_FP=("llm_FP", "sum"))
        t["casc_minus_llm_errors"] = (t.casc_FN + t.casc_FP) - (t.llm_FN + t.llm_FP)
        t = t.sort_values("casc_minus_llm_errors", ascending=False)
        print("\n" + "=" * 100 + f"\n{name}  (lo={lo}, hi={hi})\n" + "=" * 100)
        print(t.to_string())
        print("\nTOTAL cascade errors:", int(t.casc_FN.sum() + t.casc_FP.sum()),
              "| LLM-on-everything errors:", int(t.llm_FN.sum() + t.llm_FP.sum()))

        lost = df[((df.final != df.y) & (df.all_llm == df.y))]
        print(f"\nPairs the cascade got wrong but LLM-on-everything got right: {len(lost)} (first 14)")
        for i in lost.index[:14]:
            print(f"  true={y[i]} cascade={final[i]} | {group[i]} | {d['left'][i][:60]} || {d['right'][i][:60]}")


if __name__ == "__main__":
    main()