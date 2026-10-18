import json
import re

import pandas as pd

from app.core.config import settings

WDC_DIR = settings.DATA_RAW_DIR / "WDC-Computers"
SIZE = "small"  # small | medium | large | xlarge (scale up later)


def clean_wdc(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x)
    s = re.sub(r"@[a-z]{2}\b", " ", s)          # language tags like "@en"
    s = re.sub(r"\bnull\b", " ", s, flags=re.I)  # literal "Null" strings
    s = s.replace('"', " ")
    return re.sub(r"\s+", " ", s).strip()


def read_gz(path) -> pd.DataFrame:
    return pd.read_json(path, lines=True, compression="gzip")


def side_records(df: pd.DataFrame, side: str) -> pd.DataFrame:
    out = pd.DataFrame({
        "record_id": "wdc:" + df[f"id_{side}"].astype(str),
        "source": "wdc",
        "brand": df[f"brand_{side}"].map(clean_wdc),
        "title": df[f"title_{side}"].map(clean_wdc),
        "description": df[f"description_{side}"].map(clean_wdc),
        # raw key-value specs, kept for Novelty 2 (NOT used for matching)
        "key_value_pairs": df[f"keyValuePairs_{side}"].map(
            lambda v: json.dumps(v) if isinstance(v, dict) else ""
        ),
    })
    out["text"] = (out["brand"] + " " + out["title"] + " " + out["description"].str[:300]).str.strip()
    return out


if __name__ == "__main__":
    train_all = read_gz(WDC_DIR / "training" / "computers_train" / f"computers_train_{SIZE}.json.gz")
    test = read_gz(WDC_DIR / "computers_gs.json.gz")
    valid_ids = set(pd.read_csv(WDC_DIR / "validation" / f"computers_valid_{SIZE}.csv", dtype=str)["pair_id"])

    train_all["pair_id"] = train_all["pair_id"].astype(str)
    assert train_all["pair_id"].is_unique, "duplicate pair_ids in training file"
    found = train_all["pair_id"].isin(valid_ids).sum()
    assert found == len(valid_ids), f"only {found} of {len(valid_ids)} validation ids found in training file"

    train_all["split"] = train_all["pair_id"].map(lambda p: "val" if p in valid_ids else "train")
    test["split"] = "test"
    allp = pd.concat([train_all, test], ignore_index=True)

    records = (
        pd.concat([side_records(allp, "left"), side_records(allp, "right")])
        .drop_duplicates("record_id", keep="first")
        .reset_index(drop=True)
    )
    pairs = pd.DataFrame({
        "left_id": "wdc:" + allp["id_left"].astype(str),
        "right_id": "wdc:" + allp["id_right"].astype(str),
        "label": allp["label"].astype(int),
        "split": allp["split"],
    })
    assert (set(pairs["left_id"]) | set(pairs["right_id"])) <= set(records["record_id"])

    settings.DATA_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    records.to_csv(settings.DATA_INTERIM_DIR / "wdc_records.csv", index=False)
    pairs.to_csv(settings.DATA_PROCESSED_DIR / "wdc_pairs.csv", index=False)

    print("records:", len(records), "| empty text:", int((records["text"] == "").sum()))
    print(pairs.groupby(["split", "label"]).size().unstack(fill_value=0))
    print("key_value_pairs coverage:", round((records["key_value_pairs"] != "").mean(), 3))