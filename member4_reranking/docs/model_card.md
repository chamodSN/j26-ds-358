# Model card – Member 4 relevance re-ranker (Novelty 1)

**Component:** M4 – Cross-encoder re-ranking (J26-DS-358, Vero) · **Owner:** Sandeepani K G J (IT23295438) · **Version:** S12, 21 Oct 2026

## What the model does
Given the **useful part of a user query** and **one product listing**, the model returns a **relevance score (0–1)** that says how well the product matches what the user asked for. M4 scores the 10–30 products that M2 sends for a query and sorts them by this score.

## Model
| Item | Value |
|---|---|
| Base model | `cross-encoder/ms-marco-MiniLM-L-6-v2` (6 layers, about 22M parameters, pre-trained for passage ranking on MS MARCO) |
| Fine-tuned run | `minilm_l6_augplus__q_focused_cat__s43`, epoch 2 (deployment copy: `models/m4_final/`, not in Git) |
| Output | one logit per (query, product) pair → `sigmoid` → relevance score 0–1 |
| Calibration | isotonic regression on ESCI validation → `P(Exact)`; stored as points in `m4_config.json` |
| Match labels | **Great** if P(Exact) ≥ 0.90 (raw score ≥ 0.953) · **Good** if ≥ 0.50 (≥ 0.424) · **Fair** otherwise |
| Speed | about **105 ms for 30 products on a laptop CPU** (batch 32, max length 256) |

## Inputs
- **Query input (`q_focused_cat`):** `query_to_text(query, price_span, category)` removes price limits/currency, price words, platform names and delivery words, and keeps product type, brand, model, specs and need words. If given, M3's category is added as a prefix, e.g. `[Mobile & Computing] redmi note 13 8gb 256gb`.
- **Product input (`full_bullets`):** `title | brand | colour | first 200 characters of features`, built from M2's fields (read-only). Listing metadata (seller, URLs, shipping, image, condition, price) is never given to the model.

## Training
- **Data:** ESCI (Amazon Shopping Queries), US, electronics subset v2.3. Train 3,714 queries / val 656 / test 1,295. Query-level split, seed 42, leak checks on query id and normalised query text.
- **Labels → targets:** Exact 1.0 · Substitute 0.1 · Complement 0.01 · Irrelevant 0.
- **Loss / settings:** BCEWithLogitsLoss with soft targets. 3 epochs, lr 2e-5, 10% warm-up + linear decay, weight decay 0.01, batch 32, fp16, max length 256. Seeds 42/43/44.
- **Product formats in training (random per row and epoch):** title · title+brand · full · full+bullets · key_value · **short title (3–8 words) + brand + colour + features** (the "augplus" format, added to reduce bias against incomplete listings).
- **Selection rules were fixed before the results** (query input, backbone, augmentation, deployment seed, label thresholds).

## Evaluation (summary – details in `results_summary.md`)
| Set | Final model | BM25 | Zero-shot MiniLM-L6 |
|---|---|---|---|
| ESCI test, 1,295 queries (used once), NDCG@10 | **0.906 ± 0.001** | 0.844 | 0.879 |
| ESCI test, small_version (507 harder queries) | **0.789 ± 0.003** | 0.679 | 0.717 |
| Synthetic marketplace set (200 listings, 20 queries) | **0.976** | 0.906 | 0.938 |

## Intended use
Re-ranking a **short candidate list (10–30 products)** for **English** electronics shopping queries inside the Vero pipeline, after retrieval (M1) and harmonization (M2).

## Not intended for
- Searching a whole catalogue (too slow; that is M1's job).
- Judging price, budget, platform or seller quality. These are handled later (Novelty 2 / offer step), never by this score.
- Non-English queries (Sinhala/Tamil script, Singlish words are not understood).

## Known limitations
1. **Incomplete listings:** listings with a very short title and no brand/features get lower scores than they deserve. Training with the augplus format reduced this bias from 0.184 to 0.040 on ESCI validation, but only from 0.26 to 0.16 on synthetic marketplace listings. Such listings are marked `low_confidence` (title < 6 words, no brand, no features). Planned fix: add M2's extracted attributes to the product text.
2. **Near-match products** (same model family, different variant) can score high on real listings (e.g. a 5G variant at 0.907). The calibrated match label ("Good", not "Great") and the rank handle this better than the raw score.
3. **Domain shift:** trained on Amazon US data. Marketplace behaviour was checked on a synthetic set and a 24-listing real pilot only. A full real-data test is planned.
4. **Calibration** was fitted and checked on the same ESCI validation set, so the reported label purity (Great = 96.4% Exact) is slightly optimistic.
5. Query cleaning uses regex rules as a stand-in for M1's extracted price span. Unknown noise patterns reach the model.

## Files
`src/cross_encoder.py` (query_to_text, product_to_text) · `src/reranker.py` (Reranker) · `api.py` (`POST /rerank`) · `models/m4_final/` (model + `m4_config.json`, from Drive) · notebooks `08`–`18`.
