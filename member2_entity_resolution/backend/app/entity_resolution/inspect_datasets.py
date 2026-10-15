import pandas as pd

from app.core.config import settings

for csv_path in sorted(settings.DATA_RAW_DIR.rglob("*.csv")):
    df = pd.read_csv(csv_path, encoding="latin1")
    print(f"\n=== {csv_path.relative_to(settings.DATA_RAW_DIR)} ===")
    print("rows:", len(df))
    print("columns:", list(df.columns))
    print("first row:", df.iloc[0].to_dict())