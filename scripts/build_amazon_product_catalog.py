
import json
import re
from pathlib import Path

from datasets import load_dataset


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = (
    PROJECT_ROOT
    / "member3_knowledge_graph"
    / "data"
    / "amazon_electronics_products.jsonl"
)

MAX_PRODUCTS = 20000

SEARCH_TERMS = {
    "keyboard", "keyboards", "mouse", "mice",
    "headset", "headsets", "headphone", "headphones",
    "earbuds", "monitor", "monitors", "laptop", "laptops",
    "webcam", "webcams", "router", "routers",
    "camera", "cameras", "charger", "chargers",
    "usb", "speaker", "speakers", "microphone",
    "microphones", "graphics card", "gpu", "ssd",
    "hard drive", "memory", "ram", "motherboard",
    "gaming", "computer", "computers", "tablet",
    "tablets", "printer", "printers", "projector",
    "power bank", "cable", "cables", "adapter",
    "adapters", "electronics",
}


def parse_price(value):
    """Return a numeric USD price, or None if unavailable."""
    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in {"none", "null", "nan"}:
        return None

    text = text.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def get_image(images):
    """Prefer high-resolution product images."""
    if not isinstance(images, dict):
        return None

    for key in ("hi_res", "large", "thumb"):
        values = images.get(key, [])

        if isinstance(values, str):
            values = [values]

        if isinstance(values, list):
            for url in values:
                if isinstance(url, str) and url.startswith("https://"):
                    return url

    return None


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("Loading Amazon Electronics metadata in streaming mode...")
    print("The initial dataset scan may take some time.")


    shard_urls = [
        (
            "https://huggingface.co/datasets/"
            "McAuley-Lab/Amazon-Reviews-2023/resolve/main/"
            f"raw_meta_Electronics/full-{i:05d}-of-00010.parquet"
        )
        for i in range(2)
    ]

    dataset = load_dataset(
        "parquet",
        data_files=shard_urls,
        split="train",
        streaming=True,
    )

    saved = 0
    scanned = 0

    with OUTPUT_FILE.open("w", encoding="utf-8") as output:
        for item in dataset:
            scanned += 1

            title = str(item.get("title") or "").strip()
            if not title:
                continue

            categories = item.get("categories") or []
            category_text = " ".join(
                str(category) for category in categories
            )
            searchable_text = f"{title} {category_text}".lower()

            if not any(term in searchable_text for term in SEARCH_TERMS):
                continue

            image_url = get_image(item.get("images"))
            price = parse_price(item.get("price"))

            product = {
                "product_id": str(item.get("parent_asin") or ""),
                "title": title,
                "platform": "amazon",
                "price": price,
                "currency": "USD" if price is not None else None,
                "image_url": image_url,
                "product_url": None,
                "category": categories,
                "store": item.get("store"),
                "rating": item.get("average_rating"),
                "rating_count": item.get("rating_number"),
                "price_is_historical": True,
            }

            output.write(
                json.dumps(product, ensure_ascii=False) + "\n"
            )
            saved += 1

            if saved % 1000 == 0:
                print(
                    f"Scanned {scanned:,} records; "
                    f"saved {saved:,} products..."
                )

            if saved >= MAX_PRODUCTS:
                break

    print(f"\nFinished. Scanned {scanned:,} records.")
    print(f"Saved {saved:,} products to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
