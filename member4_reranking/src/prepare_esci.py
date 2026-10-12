"""
Member 4 - Prepare the ESCI ELECTRONICS subset for cross-encoder training.
Run from repo root:  python member4_reranking/src/prepare_esci.py

Steps
 1. Keep product_locale == "us" and small_version == 1 (the standard Task-1 set).
 2. Join product text (title, brand, color, bullet points).
 3. Electronics filter (ESCI has no category column), decided per QUERY.
    share = fraction of the query's relevant (E/S) product titles that look electronic.
      keep if  share >= --min-share                                   (titles agree)
           or  query text matches  AND  share >= --min-share-qmatch   (query + some title evidence)
    Known false-positive phrases (mickey mouse, kindle books, dvd movies, "3 pc" sets,
    waist sizes like "34w" ...) are removed from the text before matching.
    All rows of a kept query are kept (also its I/C products), so ranking metrics
    (MRR, NDCG@10, P@5) are still computed over the full candidate list.
 4. Subcategory tag per query (smartphone, laptop, tablet, audio, wearable, tv_monitor,
    power_charging, camera, accessory, other_electronics) for per-subcategory metrics.
    Taken from the query text; if the query names none, from the majority of E/S titles.
 5. Labels: E=1.0, S=0.1, C=0.01, I=0.0.
 6. Splits: ESCI "test" -> test. ESCI "train" -> train + dev (dev = --dev-frac of
    train QUERIES, grouped by query, so no query leaks between splits).

Outputs (member4_reranking/data/processed/, gitignored):
  esci_elec_{train,dev,test}.parquet   (+ column 'subcategory')
  esci_elec_stats.json
  filter_review_kept.csv / filter_review_dropped.csv  (samples for manual precision check)
"""

import argparse
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

M4_DIR = Path(__file__).resolve().parents[1]
ESCI_DIR = M4_DIR / "data" / "esci"
OUT_DIR = M4_DIR / "data" / "processed"

LABEL_MAP = {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0}

# ---------------------------------------------------------------------------
# Keywords per subcategory (whole-word, case-insensitive). Order matters for
# tagging: the first subcategory that matches wins, so 'accessory' comes first
# ("iphone 8 case" is an accessory, not a smartphone).
# Ambiguous single words (case, cover, ram, echo, lens, band, switch, receiver,
# notebook, apple, watch, stand) are only used inside longer phrases.
# ---------------------------------------------------------------------------
SUBCATEGORY_KEYWORDS = {
    "accessory": [
        "phone case", "iphone case", "ipad case", "tablet case", "airpods case", "laptop case",
        "case for iphone", "case for ipad", "case for galaxy", "case for samsung", "case for pixel",
        "screen protector", "tempered glass", "phone holder", "phone mount", "phone stand",
        "car mount", "popsocket", "popsockets", "tablet stand", "laptop stand", "laptop sleeve",
        "keyboard cover", "apple watch band", "apple watch bands", "fitbit band", "smartwatch band",
        "galaxy watch band",
        "stylus", "apple pencil", "cable", "cables", "adapter", "hdmi", "dongle", "usb hub",
        "docking station", "ink cartridge", "ink cartridges", "toner cartridge", "mouse pad",
        "mousepad", "tv wall mount", "tv mount", "selfie stick", "otterbox", "spigen", "lifeproof",
    ],
    "smartphone": [
        "phone", "phones", "smartphone", "smartphones", "cell phone", "cellphone", "iphone",
        "android phone", "samsung galaxy", "galaxy s\\d+", "galaxy note", "galaxy a\\d+",
        "galaxy z", "pixel \\d+", "google pixel", "oneplus", "xiaomi", "redmi", "motorola",
        "moto g", "huawei", "nokia", "unlocked",
    ],
    "laptop": [
        "laptop", "laptops", "notebook computer", "macbook", "chromebook", "thinkpad",
        "ultrabook", "gaming laptop", "zenbook", "vivobook", "ideapad", "xps 13", "xps 15",
        "surface laptop", "surface book",
    ],
    "tablet": [
        "tablet", "ipad", "ipad pro", "ipad air", "ipad mini", "galaxy tab",
        "fire hd", "fire tablet", "kindle fire", "kindle paperwhite", "kindle oasis",
        "e-reader", "ereader", "surface pro",
    ],
    "audio": [
        "headphone", "headphones", "headset", "headsets", "earbuds", "earbud", "earphones",
        "earphone", "airpods", "airpod", "in-ear", "over-ear", "noise cancelling",
        "noise canceling", "speaker", "speakers", "soundbar", "sound bar", "subwoofer",
        "amplifier", "guitar amp", "headphone amp", "av receiver", "stereo receiver", "stereo", "microphone", "mic",
        "turntable", "record player", "dac", "hifi", "hi-fi", "audio", "bose", "jbl",
        "sennheiser", "skullcandy", "beats", "jabra", "sonos", "soundcore", "audio-technica",
        "audiotechnica", "altavoz", "audifonos", "auriculares",
    ],
    "wearable": [
        "smartwatch", "smart watch", "smartwatches", "apple watch", "galaxy watch", "fitbit",
        "garmin", "fitness tracker", "activity tracker", "smart band", "mi band", "amazfit",
        "whoop", "oura ring",
    ],
    "tv_monitor": [
        "tv", "tvs", "television", "smart tv", "oled", "qled", "monitor", "monitors",
        "gaming monitor", "projector", "projectors", "roku", "fire stick", "firestick",
        "fire tv", "chromecast", "apple tv", "streaming device", "vizio", "hisense", "tcl",
    ],
    "power_charging": [
        "charger", "chargers", "charging", "power bank", "powerbank", "portable charger",
        "battery pack", "power strip", "surge protector", "ups battery backup", "batteries",
        "rechargeable battery", "rechargeable batteries", "wireless charger", "power supply",
        "anker",
    ],
    "camera": [
        "camera", "cameras", "dslr", "mirrorless", "gopro", "go pro", "camcorder",
        "camera lens", "drone", "drones", "dji", "dash cam", "dashcam", "security camera",
        "webcam", "nikon", "canon eos", "sony alpha", "instax", "polaroid", "action camera",
        "ring doorbell", "video doorbell", "doorbell camera", "blink",
    ],
    "other_electronics": [
        # computers & parts, networking, storage, printing
        "computer", "computers", "desktop computer", "gaming pc", "mini pc", "pc", "keyboard",
        "keyboards", "mechanical keyboard", "computer mouse", "gaming mouse", "wireless mouse",
        "gpu", "graphics card", "rtx", "geforce", "radeon", "nvidia", "cpu", "processor", "ryzen",
        "intel core", "motherboard", "ssd", "hdd", "hard drive", "nvme", "m.2", "flash drive",
        "usb", "thumb drive", "sd card", "micro sd", "microsd", "microsdxc", "memory card",
        "ddr3", "ddr4", "ddr5", "cpu cooler", "aio cooler", "router", "routers", "mesh wifi",
        "wifi", "wi-fi", "modem", "ethernet", "network switch", "ethernet switch",
        "network card", "printer", "printers", "scanner", "mac mini", "imac", "mac pro",
        "logitech", "razer", "corsair",
        # gaming hardware
        "console", "playstation", "ps4", "ps5", "xbox", "nintendo", "nintendo switch",
        "gamecube", "game controller", "controller", "vr headset", "oculus", "steam deck",
        # home media and smart home
        "dvd player", "blu-ray player", "bluray player", "media player", "alexa", "echo dot",
        "echo show", "google home", "google nest", "smart plug", "smart bulb", "smart home",
        "baby monitor", "walkie talkie", "radio", "gps",
        "electronics", "electronic", "bluetooth",
    ],
}

# Spec tokens such as "128gb", "5000 mah", "144hz", "48mp", "1tb", "4k", "1080p".
# NOT "w"/"watt": that matched pants waist sizes ("34W x 30L") and light bulbs.
SPEC_PATTERN = r"\b\d+\s?(?:gb|tb|mah|hz|mp)\b|\b4k\b|\b8k\b|\b1080p\b|\b1440p\b|\b2160p\b"

# Phrases removed from text BEFORE matching (they contain an electronics word but are not
# electronics). Found in the Step-0 review of KEPT samples.
FALSE_POSITIVE_PHRASES = [
    r"\d+\s?(?:pc|pcs|piece|pieces)\b",          # "3 pc set", "116 pc dinnerware"
    r"\d+\s?(?:w|l)\s?x\s?\d+\s?(?:w|l)?\b",      # "34w x 30l" pant sizes
    r"mickey mouse", r"minnie mouse", r"mouse trap", r"mouse traps", r"mice",
    r"kindle (?:books?|edition|unlimited|version|ebooks?)", r"for kindle", r"books? kindle",
    r"tv (?:shows?|series|movies?|seasons?)", r"as seen on tv", r"tv tray", r"tv stand",
    r"tv console", r"console table", r"sofa console", r"center console", r"boat console",
    r"gaming (?:chair|desk|table)", r"computer (?:desk|chair|table)", r"desktop organizer",
    r"galaxy (?:costume|shirt|dress|tutu|leggings|print|crop top|railways|projector|lamp|light)",
    r"charging handle", r"cable knit", r"cable machine", r"cable ties?", r"jumper cables?",
    r"laptop (?:bag|backpack|briefcase|tote)", r"camera bag", r"glam glow", r"facial toner",
    r"wireless bra", r"radio flyer", r"\d+\s?(?:count|ct)?\s?tablets?", r"lazy susan",
    r"turntable bearing", r"cake turntable", r"\d+\s?amps?\b",
]

# If a text contains one of these, it is NOT electronics (whole text vetoed).
# Pills, adult toys and battery power tools carry words like "usb", "charger", "tablet".
NON_ELECTRONIC_VETO = [
    r"melatonin", r"vitamins?", r"supplements?", r"capsules?", r"chewable", r"dissolving",
    r"vibrators?", r"dildos?", r"sex toys?", r"adult toys?", r"clitoral",
    r"mowers?", r"leaf blower", r"chainsaws?", r"string trimmer", r"hedge trimmer",
    r"impact driver", r"drill", r"wet saw", r"circular saw",
    r"lazy susan", r"tattoo", r"faucet", r"spice rack",
]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
FP_RE = re.compile(r"\b(?:" + "|".join(FALSE_POSITIVE_PHRASES) + r")", flags=re.IGNORECASE)
VETO_RE = re.compile(r"\b(?:" + "|".join(NON_ELECTRONIC_VETO) + r")\b", flags=re.IGNORECASE)


def _kw_regex(words) -> str:
    # keywords may contain small regex parts (e.g. "galaxy s\\d+"); spaces stay literal
    return r"\b(?:" + "|".join(w for w in words) + r")\b"


SUBCAT_RES = {s: re.compile(_kw_regex(w), re.IGNORECASE) for s, w in SUBCATEGORY_KEYWORDS.items()}
ALL_KW = [w for ws in SUBCATEGORY_KEYWORDS.values() for w in ws]
KW_REGEX = re.compile(_kw_regex(ALL_KW) + "|" + SPEC_PATTERN, flags=re.IGNORECASE)


def strip_false_positives(text: pd.Series) -> pd.Series:
    return text.fillna("").str.replace(FP_RE, " ", regex=True)


def is_electronic(text: pd.Series) -> pd.Series:
    t = text.fillna("")
    return strip_false_positives(t).str.contains(KW_REGEX) & ~t.str.contains(VETO_RE)


# Tagging only (does not change which queries are kept): these words make it an accessory
# ("iphone 11 case", "samsung watch bands"), and a few phrases are pinned to a subcategory.
ACCESSORY_WORDS_RE = re.compile(
    r"\b(?:cases?|covers?|skins?|protectors?|bands?|straps?|holsters?|mounts?|sleeves?)\b",
    re.IGNORECASE)
PINNED_TAGS = {"other_electronics": re.compile(r"\bbaby monitor|fish ?finder|\bmouse\b", re.I),
               "wearable": re.compile(r"\b(?:samsung|galaxy|smart)\s?(?:\w+\s)?watch", re.I)}


def tag_subcategory(text: str) -> str | None:
    t = FP_RE.sub(" ", text or "")
    if not KW_REGEX.search(t):
        return None
    if ACCESSORY_WORDS_RE.search(t):
        return "accessory"
    for s, rx in PINNED_TAGS.items():
        if rx.search(t):
            return s
    for s, rx in SUBCAT_RES.items():
        if rx.search(t):
            return s
    return "other_electronics" if re.search(SPEC_PATTERN, t, re.IGNORECASE) else None


def clean(s) -> str:
    if not isinstance(s, str):
        return ""
    s = html.unescape(TAG_RE.sub(" ", s))
    return WS_RE.sub(" ", s).strip()


def build_product_text(df: pd.DataFrame, max_chars: int) -> pd.Series:
    """'title | Brand: x | Color: y | bullets...' cut to max_chars."""
    parts = []
    for title, brand, color, bullets in zip(
        df["product_title"], df["product_brand"], df["product_color"], df["product_bullet_point"]
    ):
        t = clean(title)
        if b := clean(brand):
            t += f" | Brand: {b}"
        if c := clean(color):
            t += f" | Color: {c}"
        if bp := clean(bullets):
            t += f" | {bp}"
        parts.append(t[:max_chars])
    return pd.Series(parts, index=df.index)


def load(esci_dir: Path) -> pd.DataFrame:
    ex = pd.read_parquet(esci_dir / "shopping_queries_dataset_examples.parquet")
    ex = ex[(ex.product_locale == "us") & (ex.small_version == 1)].copy()
    print(f"us + small_version=1: {len(ex):,} rows, {ex.query_id.nunique():,} queries")

    cols = ["product_id", "product_locale", "product_title", "product_brand",
            "product_color", "product_bullet_point"]
    pr = pd.read_parquet(
        esci_dir / "shopping_queries_dataset_products.parquet",
        columns=cols,
        filters=[("product_locale", "==", "us")],
    )
    pr = pr[pr.product_id.isin(set(ex.product_id))]
    df = ex.merge(pr, on=["product_id", "product_locale"], how="left")
    missing = df.product_title.isna().sum()
    if missing:
        print(f"warning: {missing:,} rows have no product text -> dropped")
        df = df[df.product_title.notna()]
    return df


def query_table(df: pd.DataFrame, min_share: float, min_share_qmatch: float) -> pd.DataFrame:
    """One row per query: text match, title share, keep decision, subcategory."""
    q = df.groupby("query_id")["query"].first().to_frame()
    q["qmatch"] = is_electronic(q["query"])
    rel = df[df.esci_label.isin(["E", "S"])]
    rel = rel.assign(m=is_electronic(rel.product_title))
    q["share"] = rel.groupby("query_id")["m"].mean().reindex(q.index, fill_value=0.0)
    q["keep"] = (q.share >= min_share) | (q.qmatch & (q.share >= min_share_qmatch))

    # subcategory: from query text, else the most common tag among electronic E/S titles
    q["subcategory"] = q["query"].map(tag_subcategory)
    need = q.keep & q.subcategory.isna()
    if need.any():
        r = rel[rel.query_id.isin(q.index[need]) & rel.m]
        tags = r.product_title.map(tag_subcategory).dropna()
        maj = tags.groupby(r.loc[tags.index, "query_id"]).agg(lambda s: s.value_counts().index[0])
        q.loc[need, "subcategory"] = maj.reindex(q.index[need]).values
    q.loc[q.keep, "subcategory"] = q.loc[q.keep, "subcategory"].fillna("other_electronics")

    print(f"electronics queries: {q.keep.sum():,} / {len(q):,} "
          f"(query text + titles: {(q.keep & q.qmatch).sum():,}, "
          f"titles only: {(q.keep & ~q.qmatch).sum():,})")
    return q


def split_dev(train: pd.DataFrame, frac: float, seed: int):
    qids = np.sort(train.query_id.unique())
    rng = np.random.default_rng(seed)
    dev_q = set(rng.choice(qids, size=max(1, int(len(qids) * frac)), replace=False))
    is_dev = train.query_id.isin(dev_q)
    return train[~is_dev], train[is_dev]


def describe(d: pd.DataFrame) -> dict:
    per_q = d.groupby("query_id")["subcategory"].first().value_counts()
    return {
        "rows": int(len(d)),
        "queries": int(d.query_id.nunique()),
        "queries_with_exact": int(d[d.esci_label == "E"].query_id.nunique()),
        "avg_products_per_query": round(len(d) / max(1, d.query_id.nunique()), 2),
        "labels": {k: int(v) for k, v in d.esci_label.value_counts().items()},
        "queries_per_subcategory": {k: int(v) for k, v in per_q.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esci-dir", type=Path, default=ESCI_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--min-share", type=float, default=0.5,
                    help="keep if this share of E/S titles look electronic")
    ap.add_argument("--min-share-qmatch", type=float, default=0.25,
                    help="lower share needed when the query text itself matches")
    ap.add_argument("--dev-frac", type=float, default=0.1)
    ap.add_argument("--max-chars", type=int, default=512)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--review-n", type=int, default=100, help="samples written for review")
    args = ap.parse_args()

    df = load(args.esci_dir)
    q = query_table(df, args.min_share, args.min_share_qmatch)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Review samples (for the manual precision check; fill the 'is_electronics' column by hand)
    for name, part in [("kept", q[q.keep]), ("dropped", q[~q.keep])]:
        s = part.sample(min(args.review_n, len(part)), random_state=args.seed)
        s.assign(is_electronics="")[["query", "qmatch", "share", "subcategory", "is_electronics"]] \
            .to_csv(args.out_dir / f"filter_review_{name}.csv")

    df = df[df.query_id.isin(q.index[q.keep])].copy()
    df["subcategory"] = df.query_id.map(q.subcategory)
    df["product_text"] = build_product_text(df, args.max_chars)
    df["label"] = df.esci_label.map(LABEL_MAP).astype("float32")
    df = df[["query_id", "query", "product_id", "product_text", "esci_label", "label",
             "subcategory", "split"]]

    train, dev = split_dev(df[df.split == "train"], args.dev_frac, args.seed)
    test = df[df.split == "test"]

    stats = {"settings": {k: str(v) for k, v in vars(args).items()}}
    for name, d in [("train", train), ("dev", dev), ("test", test)]:
        d.reset_index(drop=True).to_parquet(args.out_dir / f"esci_elec_{name}.parquet", index=False)
        stats[name] = describe(d)
    (args.out_dir / "esci_elec_stats.json").write_text(json.dumps(stats, indent=2))

    print("\n" + json.dumps({k: v for k, v in stats.items() if k != "settings"}, indent=2))
    print(f"\nSaved to {args.out_dir}")


if __name__ == "__main__":
    main()