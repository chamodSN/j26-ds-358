# member4_reranking/data

This folder is **empty on purpose**. The datasets are too large for Git, and `.gitignore` blocks `**/data/**` (except this README and `.gitkeep`).

## Where the data is
Google Drive `MyDrive/esci/` (shared folder; add a shortcut to "My Drive" so the path stays the same in Colab):

| Path | Content |
|---|---|
| `data/` | raw ESCI download (amazon-science/esci-data) |
| `dataset_v2.3/` | `esci_electronics_v2.3_queries.parquet`, `_judgments.parquet`, `_corpus.parquet`, `card.json` |
| `processed/rerank_pairs_v2.3.parquet` | one row per (query, product) with label, gain and `part` = train / val / test |
| `processed/val_query_ids_seed42.csv` | the validation query ids |
| `code/` | copies of `src/*.py` that Colab imports |
| `models/` | training runs (`<run>/epoch_<n>/`) and the deployment model `m4_final/` |
| `results/` | logs and result CSVs (small ones are also committed in `member4_reranking/results/`) |
| `s11/` | S11 evaluation files |

## How to rebuild
1. Notebook `02_ESCI_dataset_v2.3_member4_run` → builds `dataset_v2.3/` from the raw ESCI files (5,665 queries, 100,740 judgments, 51,318 products).
2. Notebook `03_rerank_data` → joins queries, judgments and products, makes the query-level split (val = 656 queries, seed 42, stratified by scope group; test = ESCI test, 1,295 queries) and runs the leak checks.

## Deployment model for the API
Copy Drive `models/m4_final/` (all files, including `model.safetensors` and `m4_config.json`) to `member4_reranking/models/m4_final/`. That folder is also ignored by Git. The API reads it at the first `/rerank` call (or from the path in the `M4_MODEL_DIR` environment variable).
