# Dataset card – data used by Member 4

## 1. ESCI electronics subset v2.3 (training, validation, test)
| Item | Value |
|---|---|
| Source | Amazon "Shopping Queries Dataset" (ESCI), `amazon-science/esci-data`, US locale |
| Subset | electronics, built by the team (notebook `02_ESCI_dataset_v2.3_member4_run`) |
| Size | 5,665 queries · 100,740 query–product judgments · 51,318 products |
| Product fields used | title, brand, colour, bullet points (first 200 characters) |
| Labels | E (Exact), S (Substitute), C (Complement), I (Irrelevant) → gains 1.0 / 0.1 / 0.01 / 0 |
| Split (query level) | train 3,714 · val 656 · test 1,295 (of which 507 are `small_version` = harder set). Val made by Member 4 with seed 42, stratified by scope group. |
| Leak checks | no query id or normalised query text appears in two parts |
| Test use | used **once** (S10), locked by `results/S10_TEST_USED.txt` |
| Category stand-in for M3 | `scope_group` mapped to 8 category names, **only for Rule A queries** (Rule B is derived from labelled products and would leak labels) |

**Notes**
- `small` (queries file) and `small_version` (judgments file) are different columns. The test hard set uses `small_version = 1`.
- 62 of 5,665 queries contain price/platform/delivery words; only 4 of 656 val queries.
- Label mix on val candidates: E 69% · S 21% · C 5% · I 5%.

**Where it is:** Google Drive `MyDrive/esci/` (`dataset_v2.3/`, `processed/rerank_pairs_v2.3.parquet`). Not in Git (size). See `data/README.md`.

## 2. S11a – synthetic marketplace-style set (evaluation only)
| Item | Value |
|---|---|
| File | `results/s11_synthetic_v1.csv` (built by `make_s11.py`) |
| Size | 20 Sri Lankan-style English queries × 10 listings = 200 rows (E 62 · S 58 · C 40 · I 40) |
| Content | Listings **written** to look like Daraz/eBay/AliExpress listings (not copied from any site). Styles: full 80 · short title + fields 60 · short only 20 · no brand 20 · noisy (caps/emoji/marketing) 20. Query noise: price numbers, Rs/$/glued LKR, cheap, platform names, delivery words, Singlish. |
| Labels | ESCI definitions; reviewed by the student |
| Limits | Synthetic, so easier than real data; 20 queries = low statistical power |

## 3. S11b – real-data pilot (evaluation only)
| Item | Value |
|---|---|
| File | `results/s11b_real_pilot.csv` |
| Size | 24 real listings, 8 real queries (collected 21 Oct 2026 by the student) |
| Sources | Daraz, eBay, AliExpress, Alibaba, Temu and Sri Lankan shops (smartmobile.lk, sellx.lk, kapruka, celltronics, banana.lk, laptop.lk, ikman.lk, abansit.lk) |
| Method | for each query, top results from several sites in the order shown; labelled E/S/C/I by the student |
| Limits | too small for NDCG or significance tests; reported as a case study. A full real test set (≥ 10 queries × 10 listings) is planned and will be used **only for testing**, never for tuning. |
