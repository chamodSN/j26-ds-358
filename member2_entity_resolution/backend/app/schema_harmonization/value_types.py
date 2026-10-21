"""Rough VALUE-TYPE detection. Prices describe the OFFER, not the product."""
import re
from collections import Counter

# Only CURRENCY values are rejected (audit on the real WDC inventory: rejecting identifier/free_text
# also dropped Dimensions, RAID Level, CAS Latency, and EAN/UPC/MPN that entity resolution needs).
NON_SPEC_TYPES = {"currency"}

_BOOL = {"yes", "no", "true", "false", "supported", "not supported", "included", "not included"}
_CURRENCY = re.compile(r"[€$£¥]|\b(usd|eur|gbp)\b", re.I)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b|"
                   r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2},? \d{4}\b", re.I)
_UNIT = r"[a-zA-Zµ°%/\"'”″]{0,8}"
_UNIT_NUM = re.compile(rf"^[~<>≈+-]?\s*\d+([.,]\d+)?\s*{_UNIT}(\s*(x|×)\s*\d+([.,]\d+)?\s*{_UNIT})*$")
_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-_/.]*")
_ID_NAME = re.compile(r"\b(id|ids|sku|ean|upc|gtin|mpn|code|serial|catalog|isbn|part|pax)\b")


def value_type(value) -> str:
    s = str(value).strip()
    if not s:
        return "empty"
    if s.lower() in _BOOL:
        return "boolean"
    if _CURRENCY.search(s):
        return "currency"
    if _DATE.search(s):
        return "date"
    if len(s) >= 45 or len(s.split()) >= 7:
        return "free_text"
    if s.isdigit() and len(s) >= 8:
        return "identifier"
    if _UNIT_NUM.match(s):
        return "numeric_unit"
    if len(s) >= 8 and " " not in s and any(c.isdigit() for c in s) and _CODE.fullmatch(s):
        return "identifier"
    return "categorical"


def cluster_value_type(samples, names) -> str:
    """Majority value type over the sample values of a candidate attribute."""
    types = [t for t in (value_type(s) for s in samples) if t != "empty"]
    return Counter(types).most_common(1)[0][0] if types else "categorical"


def attribute_role(names, vtype) -> str:
    """identifier | descriptive | spec  (a TAG kept in the registry, not a filter)."""
    if any(_ID_NAME.search(n) for n in names):
        return "identifier"
    return "descriptive" if vtype == "free_text" else "spec"