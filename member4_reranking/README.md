# Member 4 - Cross-encoder re-ranking (Sandeepani K G J, IT23295438)

Novelty 1: Cross-Encoder Re-ranking on Schema-Inconsistent Multi-Platform Candidates.

## Where things live
| What | Where |
|---|---|
| Code, notebooks, small split files, result tables | this folder (git) |
| Raw ESCI, dataset v2.3 parquet, trained models | Google Drive `MyDrive/esci/` (NOT in git) |
| Training | Google Colab (T4 GPU) |

## Local setup (VS Code) - use Python 3.11 (same as Docker; pinned packages fail on 3.13)
```
py -3.11 -m venv .venv            # Mac/Linux: python3.11 -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r member4_reranking/requirements-dev.txt
pytest member4_reranking/tests -q
```

## Branches
`member4/cross_encoder` -> PR -> `member4/reranking` -> PR -> `main`

## Notes
`.gitignore` blocks `*.ipynb` and `*.csv`, so add notebooks and split files with `git add -f`.
Never commit `.parquet`, model weights, or `.env`.
