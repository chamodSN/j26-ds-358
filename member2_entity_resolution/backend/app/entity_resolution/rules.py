import re

ACCEPT, REJECT, UNDECIDED = 1, 0, -1

# --------------------------------------------------
# Regular expressions
# --------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+(?:[-./][a-z0-9]+)*")

# Ignore pack counts like 2pack, 5pack.
_PACK = re.compile(r"^\d+pack$")

_UNITS = (
    r"(?:gb|tb|mb|kb|mhz|ghz|hz|rpm|mm|cm|nm|"
    r"inch|in|ft|mah|w|v|lb|lbs|oz|kg|g|ms|"
    r"mbs|gbs|pin|p|x|cfm|btu)"
)

_SPEC = [
    re.compile(rf"^\d+(?:\.\d+)?{_UNITS}$"),
    re.compile(r"^\d+x\d+(?:gb|mb|tb)?$"),
    re.compile(r"^\d+gbx\d+$"),
    re.compile(r"^g?ddr\d.*$"),
    re.compile(r"^pc\d{3,6}.*$"),
    re.compile(r"^cl\d+.*$"),
    re.compile(r"^\d+rx\d+$"),
    re.compile(r"^lga\d+$"),
    re.compile(r"^\d{3,4}[pi]$"),
    re.compile(r"^.*\d(?:mhz|ghz)$"),
    # lens aperture such as f/4-5.6 (a specification, not a model)
    re.compile(r"^f/?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?$"),
]

_COLOURS = {
    "black", "white", "silver", "gold", "blue", "red",
    "green", "plum", "graphite", "grey", "gray",
    "pink", "purple", "orange", "yellow", "brown",
    "bisque", "bronze", "copper", "ivory", "beige",
    "navy",
}

_WORD = re.compile(r"[a-z]+")

_CAPACITY = re.compile(
    r"(\d+(?:\.\d+)?)[\s-]?(gb|tb|mb)\b"
)

_KIT_A = re.compile(
    r"(\d+)\s?x\s?(\d+(?:\.\d+)?)\s?(gb|tb|mb)\b"
)

_KIT_B = re.compile(
    r"(\d+(?:\.\d+)?)\s?(gb|tb|mb)\s?x\s?(\d+)\b"
)

_TO_GB = {
    "mb": 1 / 1024,
    "gb": 1.0,
    "tb": 1024.0,
}


# --------------------------------------------------
# Model token extraction
# --------------------------------------------------

def _is_spec(raw: str, normalized: str) -> bool:
    """Return True for specification-like tokens."""
    return any(
        pattern.fullmatch(raw) or pattern.fullmatch(normalized)
        for pattern in _SPEC
    )


def model_tokens(text: str) -> set:
    """
    Extract model-number-like tokens.

    Examples:
        KC-C100U  -> kcc100u
        DSC-W150  -> dscw150
        9N00.101  -> 9n00101
        3741001   -> 3741001   (long all-digit codes are kept)

    Ignore:
        8GB, DDR4, 2400MHz, 2pack, 5pack, f/4-5.6
    """
    result = set()

    for raw in _TOKEN.findall(str(text).lower()):
        normalized = re.sub(r"[-./]", "", raw)

        digits = sum(c.isdigit() for c in normalized)
        letters = sum(c.isalpha() for c in normalized)

        code_like = (
            (len(normalized) >= 4 and digits >= 2 and letters >= 1)
            or (normalized.isdigit() and len(normalized) >= 6)
        )

        if (
            code_like
            and not _is_spec(raw, normalized)
            and not _PACK.fullmatch(normalized)
        ):
            result.add(normalized)

    return result


def _primary(tokens: set) -> str:
    """
    Most specific model token = the longest one.
    Shared family names (ML350, E310, G6) are shorter than the real code.
    """
    return max(tokens, key=lambda t: (len(t), t))


# --------------------------------------------------
# Capacity extraction
# --------------------------------------------------

def capacities(text: str) -> set:
    """
    Extract memory/storage capacity in GB.

    Examples:
        8GB   -> 8.0
        1TB   -> 1024.0
        2x4GB -> 8.0 (also retains 4.0)
    """
    text = str(text).lower()
    values = set()

    for value, unit in _CAPACITY.findall(text):
        values.add(round(float(value) * _TO_GB[unit], 3))

    for count, value, unit in _KIT_A.findall(text):
        total = int(count) * float(value) * _TO_GB[unit]
        values.add(round(total, 3))

    for value, unit, count in _KIT_B.findall(text):
        total = float(value) * _TO_GB[unit] * int(count)
        values.add(round(total, 3))

    return values


# --------------------------------------------------
# Model relation checking
# --------------------------------------------------

def _relation(x: str, y: str) -> str:
    """
    Compare two model codes.

    Returns: same | variant | partial | near_miss | different
    """
    if x == y:
        return "same"

    common = 0

    for a, b in zip(x, y):
        if a != b:
            break
        common += 1

    rx = x[common:]
    ry = y[common:]

    # Suffix-only differences (colour / region codes)
    if (
        common >= 4
        and len(rx) <= 4
        and len(ry) <= 4
        and (not rx or rx.isalpha())
        and (not ry or ry.isalpha())
    ):
        return "variant"

    # One code contains the other (6850k inside bx80671i76850k)
    short, long_ = sorted((x, y), key=len)
    if len(short) >= 5 and short in long_:
        return "partial"

    # Very similar model numbers
    if (
        len(x) == len(y)
        and len(x) >= 5
        and sum(a != b for a, b in zip(x, y)) <= 2
    ):
        return "near_miss"

    return "different"


# --------------------------------------------------
# Colour checking
# --------------------------------------------------

def _colour_words(text: str) -> set:
    words = set(_WORD.findall(str(text).lower()))
    return words & _COLOURS


# --------------------------------------------------
# Main matching decision
# --------------------------------------------------

def verdict(left_title: str, right_title: str):
    """
    Compare two product titles.

    Returns (ACCEPT | REJECT | UNDECIDED, reason).
    """
    left_models = model_tokens(left_title)
    right_models = model_tokens(right_title)

    left_caps = capacities(left_title)
    right_caps = capacities(right_title)

    capacity_conflict = bool(
        left_caps
        and right_caps
        and not (left_caps & right_caps)
    )

    left_colours = _colour_words(left_title)
    right_colours = _colour_words(right_title)

    colour_conflict = bool(
        left_colours
        and right_colours
        and not (left_colours & right_colours)
    )

    if left_models and right_models:
        # Judge identity on the most specific code of each title
        relation = _relation(_primary(left_models), _primary(right_models))

        if relation == "same":
            if colour_conflict:
                return UNDECIDED, "colour_variant"
            if capacity_conflict:
                return UNDECIDED, "capacity_conflict"
            return ACCEPT, "model_same"

        if relation == "variant":
            return UNDECIDED, "model_variant"

        if relation == "partial":
            return UNDECIDED, "model_partial"

        if relation == "near_miss":
            return REJECT, "model_near_miss"

        # Primary codes differ, but a title can list several codes
        others = {
            _relation(x, y)
            for x in left_models
            for y in right_models
        }
        if others & {"same", "variant", "partial"}:
            return UNDECIDED, "model_partial"

        return REJECT, "model_different"

    if capacity_conflict:
        return UNDECIDED, "capacity_conflict"

    return UNDECIDED, "no_evidence"


# --------------------------------------------------
# Apply rules to candidate pairs
# --------------------------------------------------

def apply_rules(pairs, title_map):
    """
    Apply matching rules to a DataFrame with columns left_id, right_id.
    Returns (verdicts, reasons).
    """
    results = [
        verdict(title_map[left_id], title_map[right_id])
        for left_id, right_id in zip(pairs["left_id"], pairs["right_id"])
    ]

    verdicts = [v for v, _ in results]
    reasons = [r for _, r in results]

    return verdicts, reasons