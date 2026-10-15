import pandas as pd

from app.core.config import settings

WDC = settings.DATA_RAW_DIR / "WDC-Computers"
files = [
    WDC / "training" / "computers_train" / "computers_train_small.json.gz",
    WDC / "computers_gs.json.gz",
]

for path in files:
    df = pd.read_json(path, lines=True, compression="gzip")
    print(f"\n=== {path.name} ===")
    print("rows:", len(df))
    print("columns:", list(df.columns))
    if "label" in df.columns:
        print("label counts:", df["label"].value_counts().to_dict())
    row = df.iloc[0].to_dict()
    print("first row (values cut to 120 chars):")
    for k, v in row.items():
        print(f"  {k}: {str(v)[:120]}")