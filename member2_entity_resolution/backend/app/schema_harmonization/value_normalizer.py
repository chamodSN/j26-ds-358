"""Minimal value normalisation: raw attribute value -> comparable value.

Why: after schema harmonization two listings can share an attribute ('capacity') but write it as '8 GB',
'8000 MB' or '2 x 4 GB'. Matching and ranking need ONE unit per measurement family.

Rules (deliberately small and explicit - every rule is visible here):
  * placeholders / corrupted values ('N/A', '-', '[email protected]' from site e-mail obfuscation) -> status "missing"
  * 'N x V unit' -> N*V unit            (2 x 4 GB -> 8 GB)
  * unit decides the family:  data (-> GB), frequency (-> MHz), rotation (RPM), throughput (-> MB/s),
                              mass (-> g), time (-> ms), power (-> W), length (-> mm), warranty (-> months)
  * anything else is kept as cleaned text with status "text" (never guessed)
Decimal comma ('1.631,0' / '4,17') and thousands separators are handled.  Data units are decimal (1 TB = 1000 GB)."""
import re

MISSING = {"", "n/a", "na", "none", "-", "--", "null", "unknown", "tbd", "?", "not applicable", "nan"}

# unit -> (family, factor to the canonical unit, canonical unit)
UNITS = {
    "kb": ("data", 1e-6, "GB"), "mb": ("data", 1e-3, "GB"), "gb": ("data", 1.0, "GB"), "tb": ("data", 1000.0, "GB"),
    "mhz": ("frequency", 1.0, "MHz"), "ghz": ("frequency", 1000.0, "MHz"),
    "rpm": ("rotation", 1.0, "RPM"),
    "kb/s": ("throughput", 1e-3, "MB/s"), "mb/s": ("throughput", 1.0, "MB/s"), "gb/s": ("throughput", 1000.0, "MB/s"),
    "mbps": ("throughput", 0.125, "MB/s"), "gbps": ("throughput", 125.0, "MB/s"),   # bits per second -> bytes
    "g": ("mass", 1.0, "g"), "kg": ("mass", 1000.0, "g"), "lb": ("mass", 453.592, "g"), "lbs": ("mass", 453.592, "g"),
    "pound": ("mass", 453.592, "g"), "pounds": ("mass", 453.592, "g"), "oz": ("mass", 28.3495, "g"), "ounce": ("mass", 28.3495, "g"),
    "µs": ("time", 1e-3, "ms"), "us": ("time", 1e-3, "ms"), "ms": ("time", 1.0, "ms"), "s": ("time", 1000.0, "ms"),
    "w": ("power", 1.0, "W"), "watt": ("power", 1.0, "W"), "watts": ("power", 1.0, "W"), "kw": ("power", 1000.0, "W"),
    "mm": ("length", 1.0, "mm"), "cm": ("length", 10.0, "mm"), "in": ("length", 25.4, "mm"), "inch": ("length", 25.4, "mm"),
    "inches": ("length", 25.4, "mm"), '"': ("length", 25.4, "mm"),
    "month": ("warranty", 1.0, "months"), "months": ("warranty", 1.0, "months"),
    "year": ("warranty", 12.0, "months"), "years": ("warranty", 12.0, "months"), "yr": ("warranty", 12.0, "months"),
}
_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_PAT = re.compile(rf"^\s*(?:(\d+)\s*[x×]\s*)?({_NUM})\s*([a-zA-Zµ\"/]+)?\s*$")


def is_missing(raw):
    s = str(raw).replace("\xa0", " ").strip().lower()
    return raw is None or s in MISSING or "[email" in s or "protected]" in s


def _number(txt):
    """'1.631,0' -> 1631.0   '4,17' -> 4.17   '1,000' -> 1000.0   '3.5' -> 3.5"""
    if "," in txt and "." in txt:                      # the LAST separator is the decimal one
        dec = "," if txt.rfind(",") > txt.rfind(".") else "."
        thou = "." if dec == "," else ","
        return float(txt.replace(thou, "").replace(dec, "."))
    if "," in txt:
        head, tail = txt.rsplit(",", 1)
        return float(txt.replace(",", "")) if len(tail) == 3 and head.isdigit() else float(txt.replace(",", "."))
    return float(txt)


def normalize_value(raw):
    """-> dict(status, value, unit, family, raw).  status: ok | text | missing."""
    out = dict(status="missing", value=None, unit="", family="", raw=raw)
    if is_missing(raw):
        return out
    s = str(raw).replace("\xa0", " ").strip()
    m = _PAT.match(s)
    if m:
        count, num, unit = m.groups()
        u = (unit or "").lower()
        if u in UNITS:
            family, factor, canon = UNITS[u]
            value = _number(num) * factor * (int(count) if count else 1)
            out.update(status="ok", value=round(value, 6), unit=canon, family=family)
            return out
    out.update(status="text", value=re.sub(r"\s+", " ", s).lower())
    return out