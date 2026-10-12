# SO1 - Fine-tuned cross-encoder vs Baseline 1 (ESCI electronics)

Data: ESCI Task-1 US electronics subset from Step 0 (test split: 1,276 queries, 23,256 rows,
about 18 candidates per query). Model selection used dev only (304 queries); test was used once, for reporting.
Metric rules: MRR and P@5 count only Exact as relevant; NDCG@10 uses gains E=1, S=0.1, C=0.01, I=0;
only queries with at least one Exact; random tie-break (seed 42). Wilcoxon signed-rank test, paired per query.
Source files: `results/eval_test.json`, `results/train_report.json`.

## Training (Colab T4, 2026-10-12)
cross-encoder/ms-marco-MiniLM-L-6-v2, BCE on soft labels, 3 epochs, lr 2e-5, batch 32,
max length 256, warmup 10%, seed 42, fp16. 6.4 minutes in total.

| Epoch | Train loss | Dev MRR | Dev NDCG@10 | Dev P@5 |
|---|---|---|---|---|
| 0 (no fine-tuning) | - | 0.8012 | 0.7365 | 0.5454 |
| 1 | 0.717 | 0.8231 | 0.7704 | 0.5829 |
| **2 (best, kept)** | 0.558 | **0.8290** | **0.7742** | **0.5862** |
| 3 | 0.520 | 0.8202 | 0.7675 | 0.5868 |

Epoch 3 is slightly worse on dev, so epoch 2 was kept (early sign of overfitting).

## Test results
| System | MRR | NDCG@10 | P@5 | CPU ms / query* |
|---|---|---|---|---|
| Random | 0.5968 | 0.5782 | 0.4252 | 0.1 |
| BM25 | 0.7229 | 0.6741 | 0.5139 | 0.6 |
| **Baseline 1** (bi-encoder all-MiniLM-L6-v2) | 0.7528 | 0.7104 | 0.5429 | 519 |
| Zero-shot cross-encoder | 0.7899 | 0.7298 | 0.5661 | 536 |
| **Fine-tuned cross-encoder (SO1)** | **0.8331** | **0.7777** | **0.6034** | 522 |

\* Mean time to score one query's ~18 candidates on the author's laptop CPU (100 queries, model already
loaded). For b1 this includes encoding the product texts; in the full system M1 has these embeddings
already, so b1's real cost is lower.

## Significance (paired Wilcoxon, test)
| Comparison | MRR diff (p) | NDCG@10 diff (p) | P@5 diff (p) |
|---|---|---|---|
| Fine-tuned vs Baseline 1 | +0.0803 (9.5e-17) | +0.0673 (1.2e-29) | +0.0605 (3.2e-17) |
| Fine-tuned vs zero-shot | +0.0433 (1.8e-07) | +0.0479 (2.4e-22) | +0.0373 (4.9e-08) |
| Zero-shot vs Baseline 1 | +0.0370 (3.4e-05) | +0.0194 (3.1e-04) | +0.0232 (1.8e-05) |

On NDCG@10 the fine-tuned model beats Baseline 1 on 784 queries, loses on 446 and ties on 46.

## Per subcategory (test NDCG@10)
| Subcategory | Queries | Baseline 1 | Fine-tuned | Gain |
|---|---|---|---|---|
| accessory | 367 | 0.7217 | 0.7847 | +0.063 |
| other_electronics | 313 | 0.7106 | 0.7733 | +0.063 |
| audio | 150 | 0.6981 | 0.7602 | +0.062 |
| smartphone | 115 | 0.7120 | 0.7977 | +0.086 |
| tv_monitor | 88 | 0.7174 | 0.7938 | +0.076 |
| camera | 83 | 0.6849 | 0.7700 | +0.085 |
| power_charging | 68 | 0.6841 | 0.7319 | +0.048 |
| laptop | 38 | 0.7576 | 0.8201 | +0.063 |
| tablet | 35 | 0.6925 | 0.7750 | +0.083 |
| wearable | 19 | 0.6866 | 0.7748 | +0.088 |

The fine-tuned model is better in every subcategory. Laptop, tablet and wearable have fewer than
40 queries each, so treat those gains as indicative only.

## What this shows (and does not)
- Re-ranking with a cross-encoder after retrieval helps (the panel's issue 1). Fine-tuning on ESCI electronics
  adds a further, significant gain on top of the zero-shot cross-encoder.
- Random already scores high (MRR 0.60) because about 43% of test candidates are Exact; compare gains against
  Baseline 1, not against zero.
- These are relevance metrics only. They say nothing about price, PPP or value (SO3 to SO5).
- Baseline 2 (same fine-tuned model without M1/M3 conditioning) is this same "fine-tuned" row; SO2 is compared against it.