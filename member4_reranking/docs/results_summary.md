# Results summary – Member 4, Novelty 1 (relevance re-ranking)

Metrics: NDCG@10 (graded gains E 1 / S 0.1 / C 0.01 / I 0), full-list MRR and P@5 (relevant = Exact only). Mean ± std over 3 seeds where shown. Paired Wilcoxon test per query. All decision rules were fixed before the results.

## S4 – baselines (validation, NDCG@10)
random 0.768 · BM25 0.872 · SBERT bi-encoder 0.883 · MiniLM-L6 zero-shot 0.912 · MiniLM-L12 zero-shot 0.914

## S7 – which query input? (MiniLM-L6, 3 seeds, val)
| Input | NDCG@10 |
|---|---|
| raw query | 0.9277 ± 0.0009 |
| raw + category | 0.9290 ± 0.0007 |
| focused (useful parts) | 0.9276 ± 0.0004 |
| **focused + category (chosen)** | 0.9279 ± 0.0010 |
All pairs p ≥ 0.29 → equal on clean ESCI queries. Chosen for the design reason (panel advice + M3 context); proven useful in S9c.

## S8 – which backbone? (focused + category, val)
MiniLM-L12 0.9291 · **MiniLM-L6 0.9279** · BERT-base 0.9251 · DistilBERT 0.9209. L12 vs L6 p = 0.79 (equal), L12 about 2× slower → **MiniLM-L6 selected**. Ranking pre-training mattered more than model size.

## S9 – robustness
| Test | Result |
|---|---|
| S9a: mixed-format vs full-only training | no difference on ESCI |
| S9a: incomplete listings (val) | normal 0.928 · no brand 0.901 · title first 4 words 0.881 · **no title 0.847** |
| S9b: title-only augmentation | no significant gain (p = 0.55) |
| **S9c: price/platform words added to queries** | raw-query model loses up to **3.8 points** ("under 60000", "on daraz"); focused model loses **0** (p < 0.0001). Rule coverage 99.8%. |
| S9d: incomplete listings in mixed lists | using all fields recovers +1.9 points; Exact items with short text ranked 18–27% of the list lower (bias) |
| **S9e: augplus training** | bias 0.184 → **0.040** (p < 0.0001); normal NDCG unchanged (p = 0.39) → **final model** |

## S10 – final test (used once, 3 seeds)
| Model | Full test (1,295 q) | small_version (507 q) |
|---|---|---|
| BM25 | 0.844 | 0.679 |
| MiniLM-L6 zero-shot | 0.879 | 0.717 |
| **Final model (augplus)** | **0.906 ± 0.001** (MRR 0.935, P@5 0.796) | **0.789 ± 0.003** |
Final vs BM25: +6.2 (p = 3e-34), +11.0 on hard queries. Final vs zero-shot: +2.7 (p = 3e-14), +7.2 on hard queries.

## S11 – marketplace-style checks
**Synthetic set (200 listings, 20 queries):** final 0.976 vs BM25 0.906 (+7.0, better on 15/20 queries, p = 0.001) and zero-shot 0.938 (+3.8, 18/20, p = 0.0006). MRR = 1.0. P@5 0.60 (ceiling about 0.62). Query cleaning 20/20. Short-listing bias: zero-shot 0.26 → final 0.16.
**Real pilot (24 listings, 8 queries):** query cleaning 8/8. "redmi note 13 8gb 256gb": all 5 Exact listings ranked first (BM25 put a Substitute above an Exact). Mean score Exact 0.996 vs Substitute 0.61. 21% of real titles had fewer than 6 words.

## S12 – deployment and match labels (ESCI validation)
- Deployment model: seed 43, epoch 2 (highest val NDCG 0.9279).
- Score by label: E median 0.971 · S 0.237 · C 0.226 · I 0.162.
- Match labels from calibrated P(Exact): **Great ≥ 0.953** (96.4% Exact) · **Good ≥ 0.424** (73.9% Exact) · **Fair** (25.2% Exact, 50.6% Substitute). Shares 41% / 30% / 29%.
- `/rerank` API: 25 tests pass; **105 ms for 30 products on CPU**.

## Main limitations
Bias against very incomplete listings only partly removed (flagged as low_confidence). Calibration checked in-sample. Real-data evidence is a small pilot. English only.
