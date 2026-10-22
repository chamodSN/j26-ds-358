import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

OUT = Path("../data/processed")
client = OpenAI()
MODEL = "gpt-4o-mini"      # <- must equal the value used in notebook 05
TEMP, MAX_TOKENS, PV = 0, 150, "v2"

PROSE_USER = "Please write a passage to answer the question.\nQuestion: {q}\nPassage:"
SPEC_SYSTEM = """You turn a shopper's electronics search query into a hypothetical Amazon US product listing (circa 2020-2021), written the way sellers write listings.
Output ONE line, max 60 words, exactly 4 fields separated by " | ":
Listing title | Brand | Key specs | Features
Rules:
1. Listing title: keyword-style title starting with the product type, including any brand/model from the query, plus 1-2 synonyms sellers use (e.g. "Webcam / Web Camera", "TV Box / Media Player", "Soundbar / Speaker System").
2. Brand = the manufacturer only if the query names the brand of the product itself. If the query names a device the product works with (iPhone, Mac Mini, Note 8, a headphone brand for replacement parts), put it in the title as "Compatible with ..." and leave Brand empty. If no brand is stated, leave Brand empty. Never write "any" and never guess a brand.
3. Copy brand, model, size, capacity and exclusions from the query. Keep exclusion wording as the shopper wrote it ("without camera" stays "without camera"). Fix obvious typos. Never change the model or generation.
4. Key specs: include only (a) values stated in the query, (b) specs you are certain define the named model, or (c) near-universal specs for the category. If the query gives no number, do NOT pick one (no storage, resolution, wattage, focal length, range). Use descriptive terms instead, or omit.
5. Do not choose a subtype the query does not indicate (zoom vs prime lens, over-ear vs earbuds, wired vs wireless, soundbar vs 5.1 system). If the query is only a brand, name that brand's two most common product types.
6. Turn vague wishes into listing words ("good battery" -> "long battery life", "light" -> "lightweight").
7. Output only the line."""

SPEC_SHOTS = [
    ("gaming phone good battery",
     "Gaming Smartphone / Android Phone | | Large 5000mAh battery, Snapdragon processor, high refresh rate display | Long battery life, fast charging, gaming mode"),
    ("samsung 970 evo 1tb",
     "Samsung 970 EVO 1TB NVMe M.2 Internal SSD | Samsung | 1TB, PCIe Gen 3.0 x4, M.2 2280, up to 3400MB/s read | Solid state drive for laptop and desktop"),
    ("iphone charger cable",
     "Lightning Cable / iPhone Charger Cord, Compatible with iPhone 11 Pro XS XR 8 7 6 iPad | | Lightning to USB-A, MFi certified | Fast charging and data sync, durable braided nylon"),
    ("nikon lens",
     "Nikon NIKKOR Camera Lens for Nikon DSLR / Mirrorless Cameras | Nikon | Autofocus, F-mount or Z-mount | Interchangeable lens, compatible with Nikon cameras"),
    ("mobile phone without camera",
     "Mobile Phone Without Camera / Basic Cell Phone | | Unlocked, GSM, no camera | Without camera, long battery life, simple button phone"),
]


def msgs(kind, q):
    if kind == "prose":
        return [{"role": "user", "content": PROSE_USER.format(q=q)}]
    m = [{"role": "system", "content": SPEC_SYSTEM}]
    for sq, sa in SPEC_SHOTS:
        m += [{"role": "user", "content": sq},
              {"role": "assistant", "content": sa}]
    return m + [{"role": "user", "content": q}]


def chat(messages):
    last = None
    for attempt in range(5):
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=TEMP, max_tokens=MAX_TOKENS)
            return r.choices[0].message.content.strip()
        except Exception as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"API failed: {last}")


def load_cache(path):
    d = {}
    if path.exists():
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            d[r["query_id"]] = r["text"]
    return d


def generate(kind, role, df, workers=8):
    path = OUT / f"hyde_{role}_{kind}_{PV}.jsonl"
    cache = load_cache(path)
    todo = [(qid, q)
            for qid, q in zip(df["query_id"], df["query"]) if qid not in cache]
    print(kind, "cached", len(cache), "| todo", len(todo))
    with ThreadPoolExecutor(workers) as ex, path.open("a", encoding="utf-8") as f:
        futs = {ex.submit(chat, msgs(kind, q)): qid for qid, q in todo}
        for fu in as_completed(futs):
            qid = futs[fu]
            txt = fu.result()
            cache[qid] = txt
            f.write(json.dumps({"query_id": int(qid), "text": txt}) + "\n")
            f.flush()
    return cache
