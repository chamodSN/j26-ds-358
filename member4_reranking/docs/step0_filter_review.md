# Step 0 - Electronics filter review (M4)

Date: 2026-10-12. Data: ESCI Shopping Queries, github.com/amazon-science/esci-data
(`shopping_queries_dataset/*.parquet`, main branch, retrieved 2026-10-12).
Subset: product_locale = us, small_version = 1 (601,354 rows, 29,844 queries).

## Filter rule (per query)
`share` = fraction of the query's Exact/Substitute product titles that look electronic.

    keep if  share >= 0.50
         or  (query text matches  AND  share >= 0.25)

Before matching, known false-positive phrases are removed (e.g. "mickey mouse",
"kindle books", "tv shows", "3 pc", "34w x 30l", "console table", "charging handle"),
and a text is vetoed if it names a non-electronics item (pills/supplements, adult toys,
mowers/drills/saws, lazy susan, tattoo, faucet). All rows of a kept query are kept.
Keywords cover all Section 3.3 subcategories, with brands and model names.

## What the review found in v0 (old filter) and fixed
| Problem in v0 | Example | Fix |
|---|---|---|
| Spec `\d+w` / `watt` matched waist sizes and bulbs | "mens lee comfort pants" (share 1.0), "7 watt led bulb" | removed `w`/`watt` from spec pattern |
| Query keyword with no electronic products | "acorn tv comedy", "roads not taken dvd" (share 0) | query match now also needs share >= 0.25 |
| Ambiguous words | mickey **mouse**, boat **console**, **galaxy** tutu, 116 **pc** dinnerware | phrase removal list |
| Movies/e-books | "game of thrones dvd", "kindle books" | `dvd`/`blu-ray` only as "dvd player"; kindle book phrases removed |
| New keywords (widening) brought pills, amps, power tools | "melatonin tablets", "200 amp fuse", "leaf blower" | veto list; no plain `tablets`/`amp`/`wireless` |

## Result
|  | v0 (old) | v1 (this) |
|---|---|---|
| Kept queries | 4,844 | 4,322 |
| Train / dev / test queries | 3,069 / 340 / 1,435 | 2,742 / 304 / 1,276 |
| Train / dev / test rows | 56,250 / 6,062 / 26,499 | 49,522 / 5,306 / 23,256 |

v0 -> v1: 630 queries removed (mostly false positives), 108 added (mostly true
electronics from the widened keywords). No query appears in more than one split. Every kept query has at least one Exact product.

## Precision check (random samples, seed 42; labelled by hand)
- KEPT sample, 100 queries: **92 electronics, 8 not** (of the 92, 5 borderline: Instax film,
  car battery charger, cake projector, hologram fan, arcade toy).
  Precision ~= 92% (95% Wilson CI about 85-96%).
- DROPPED sample, 100 queries: **0 electronics** (appliances and power tools are out of scope).
  So at most about 3% of dropped queries are electronics (rule of three), i.e. recall is high
  but cannot be measured exactly from 100 samples.
- Remaining errors are lamps/LED strips, small kitchen gadgets, RC toys, car wiring and paper products.
- Labels: `data/processed/filter_review_kept.csv`, `filter_review_dropped.csv` (column `is_electronics`).
  Labels were proposed by the assistant and should be checked by the author.

## Subcategory tags (queries)
| Subcategory | train | dev | test |
|---|---|---|---|
| accessory (cases, cables, bands, mounts) | 798 | 91 | 367 |
| other_electronics (PC parts, gaming, networking, smart home) | 710 | 75 | 313 |
| audio | 285 | 36 | 150 |
| smartphone | 258 | 30 | 115 |
| camera | 183 | 17 | 83 |
| tv_monitor | 182 | 9 | 88 |
| power_charging | 117 | 16 | 68 |
| laptop | 93 | 21 | 38 |
| wearable | 61 | 4 | 19 |
| tablet | 55 | 5 | 35 |

Tag = first matching subcategory in the query text (case/cover/band/strap words -> accessory);
if the query names none, the most common tag of its electronic E/S titles. Tags are heuristic.
Dev has very few wearable/tablet queries, so per-subcategory numbers are reported on test only.

## Decisions taken (to confirm)
- Accessories (phone cases, cables, chargers, watch bands) are **kept** and tagged `accessory`
  (Section 3.3 "Other ... accessories, cables, cases": relevance + affordability only).
- Video games and game consoles are kept (`other_electronics`). Movies, music CDs and e-books are dropped.
- Appliances (fridges, blenders, fireplaces), power tools and lighting are out of scope.
- Dev split now sorts query ids before sampling, so it is reproducible regardless of row order.

## Limitation for the report
ESCI has no category column; this is a keyword heuristic with ~92% sampled precision.