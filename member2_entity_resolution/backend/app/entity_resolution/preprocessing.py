import re

import pandas as pd

from app.core.config import settings

DATASETS = {
    "abt_buy": {
        "folder": "Abt-Buy",
        "left": {"file": "Abt.csv", "source": "abt", "title_col": "name"},
        "right": {"file": "Buy.csv", "source": "buy", "title_col": "name"},
        "map_cols": ("idAbt", "idBuy"),
    },
    "amazon_google": {
        "folder": "Amazon-GoogleProducts",
        "left": {"file": "Amazon.csv", "source": "amazon", "title_col": "title"},
        "right": {"file": "GoogleProducts.csv", "source": "google", "title_col": "name"},
        "map_cols": ("idAmazon", "idGoogleBase"),
    },
}


def clean_text(x) -> str:
    """Collapse whitespace; missing values become an empty string."""
    return re.sub(r"\s+", " ", str(x)).strip()


def load_side(folder, spec) -> pd.DataFrame:
    # dtype=str keeps IDs as text so they join with the mapping file
    df = pd.read_csv(folder / spec["file"], encoding="latin1", dtype=str).fillna("")
    out = pd.DataFrame({
        "record_id": spec["source"] + ":" + df["id"].str.strip(),
        "source": spec["source"],
        "title": df[spec["title_col"]].map(clean_text),
        "description": df["description"].map(clean_text),
        # Abt has no manufacturer column at all -> empty string
        "manufacturer": df["manufacturer"].map(clean_text) if "manufacturer" in df.columns else "",
        "price": pd.to_numeric(df["price"], errors="coerce"),
    })
    # Text that Phase 2 will embed: manufacturer + title + description
    out["text"] = (out["manufacturer"] + " " + out["title"] + " " + out["description"]).str.strip()
    return out


def build_dataset(name: str, cfg: dict):
    folder = settings.DATA_RAW_DIR / cfg["folder"]
    left = load_side(folder, cfg["left"])
    right = load_side(folder, cfg["right"])
    records = pd.concat([left, right], ignore_index=True)

    mapping_path = next(folder.glob("*perfectMapping.csv"))  # one file has a typo'd name
    m = pd.read_csv(mapping_path, encoding="latin1", dtype=str)
    lc, rc = cfg["map_cols"]
    matches = pd.DataFrame({
        "left_id": cfg["left"]["source"] + ":" + m[lc].str.strip(),
        "right_id": cfg["right"]["source"] + ":" + m[rc].str.strip(),
        "label": 1,
    })

    # ---- sanity checks: fail loudly instead of silently ----
    assert records["record_id"].is_unique, f"{name}: duplicate record_ids"
    ids = set(records["record_id"])
    bad = ~(matches["left_id"].isin(ids) & matches["right_id"].isin(ids))
    assert not bad.any(), f"{name}: {bad.sum()} matches point to unknown records"

    return records, matches


if __name__ == "__main__":
    settings.DATA_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    for name, cfg in DATASETS.items():
        records, matches = build_dataset(name, cfg)
        records.to_csv(settings.DATA_INTERIM_DIR / f"{name}_records.csv", index=False)
        matches.to_csv(settings.DATA_INTERIM_DIR / f"{name}_matches.csv", index=False)
        print(f"{name}: {len(records)} records, {len(matches)} true matches")
        print(records[["record_id", "title", "manufacturer", "price"]].head(3).to_string(index=False))