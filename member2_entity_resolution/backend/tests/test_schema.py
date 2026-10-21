
import re
import zlib

import numpy as np
import pandas as pd

from app.schema_harmonization.attribute_inventory import (
    build_inventory,
    normalise_name,
    parse_kvp,
)
from app.schema_harmonization.attribute_matcher import (
    AMBIGUOUS,
    KNOWN,
    NEW,
    AttributeMatcher,
    classify,
)
from app.schema_harmonization.schema_growth import (
    coverage,
    grow_schema,
    harmonize_record,
)
from app.schema_harmonization.schema_registry import SchemaRegistry

from app.schema_harmonization.schema_growth import conflicts


def fake_embed(texts):
    out = []
    for t in texts:
        v = np.zeros(128, dtype=np.float32)

        for w in re.findall(r"[a-z0-9]+", t.lower()):
            v[zlib.crc32(w.encode()) % 128] += 1

        n = np.linalg.norm(v)
        out.append(v / n if n else v)

    return np.array(out)


def inv(rows):
    return pd.DataFrame([
        dict(
            name_norm=normalise_name(n),
            display_name=n,
            count=c,
            samples=s,
        )
        for n, c, s in rows
    ])


def test_normalise_and_parse():
    assert normalise_name("Memory Type *") == "memory type"
    assert normalise_name("memory-type") == "memory type"

    assert parse_kvp('{"Brand": "Kingston", "X": null}') == {
        "Brand": "Kingston"
    }

    assert parse_kvp("{'Brand': 'Kingston'}") == {
        "Brand": "Kingston"
    }

    assert parse_kvp(float("nan")) == {}
    assert parse_kvp(None) == {}
    assert parse_kvp("") == {}
    assert parse_kvp([["a", "b"]]) == {"a": "b"}


def test_classify_two_thresholds():
    assert classify(0.9, 0.4, 0.7) == KNOWN
    assert classify(0.2, 0.4, 0.7) == NEW
    assert classify(0.5, 0.4, 0.7) == AMBIGUOUS


def test_inventory_counts_records_not_occurrences():
    rec = pd.DataFrame({
        "key_value_pairs": [
            '{"Brand": "A", "brand": "B"}',
            '{"Brand": "A"}',
            "",
        ]
    })

    i = build_inventory(rec)

    assert len(i) == 1
    assert i.iloc[0]["count"] == 2


def test_alias_is_known_and_promotion_needs_support():
    reg = SchemaRegistry.from_seed()
    m = AttributeMatcher(reg, fake_embed)

    table = inv([
        ("Manufacturer", 9, ["Kingston"]),
        ("Latency", 6, ["CL16"]),
        ("Memory Latency", 2, ["CL16"]),
        ("Weird Thing", 1, ["zzz"]),
    ])

    df, mapping = grow_schema(
        table,
        reg,
        m,
        tau_new=0.4,
        tau_known=0.7,
        min_support=5,
    )

    st = dict(zip(df.display_name, df.status))

    assert st["Manufacturer"] == "known"
    assert mapping["manufacturer"] == "brand"

    assert st["Latency"] == "promoted"
    assert st["Memory Latency"] == "promoted"

    assert mapping["latency"] == mapping["memory latency"] == "latency"

    assert st["Weird Thing"] == "pending_low_support"
    assert "weird thing" not in mapping

    assert reg.version == 2
    assert "latency" in reg.attributes

    assert reg.changelog[-1]["action"] == "attribute_added"
    assert reg.changelog[-1]["support"] == 8


def test_ambiguous_never_added():
    reg = SchemaRegistry.from_seed()
    m = AttributeMatcher(reg, fake_embed)

    table = inv([
        ("Memory Capacity", 50, ["8 GB"]),
    ])

    df, _ = grow_schema(
        table,
        reg,
        m,
        tau_new=0.05,
        tau_known=0.99,
        min_support=1,
    )

    assert df.iloc[0]["status"] == "review_queue"
    assert reg.version == 1


def test_harmonize_backfill_and_roundtrip(tmp_path):
    reg = SchemaRegistry.from_seed()
    m = AttributeMatcher(reg, fake_embed)

    table = inv([
        ("Manufacturer", 3, ["Kingston"]),
        ("Latency", 6, ["CL16"]),
    ])

    _, mapping = grow_schema(table, reg, m, 0.4, 0.7, 5)

    rec = (
        '{"Manufacturer": "Kingston", '
        '"Latency": "CL16", "Odd": "x"}'
    )

    out = harmonize_record(rec, mapping)

    assert out["canonical"] == {
        "brand": "Kingston",
        "latency": "CL16",
    }

    assert out["unmapped"] == {
        "Odd": "x"
    }

    seed_only = {
        k: v for k, v in mapping.items()
        if v != "latency"
    }

    assert (
        coverage([rec], mapping)["mean_canonical_per_listing"]
        > coverage([rec], seed_only)["mean_canonical_per_listing"]
    )

    p = tmp_path / "s.json"
    reg.save(p)

    loaded = SchemaRegistry.load(p)

    assert loaded.version == reg.version
    assert "latency" in loaded.attributes


# -------------------------------------------------------
# NEW TEST: Contrast Guard Debugging
# -------------------------------------------------------

def test_contrast_guard_keeps_min_and_max_apart():
    reg = SchemaRegistry.from_seed()
    m = AttributeMatcher(reg, fake_embed)

    table = inv([
        ("Min Operating Temperature", 10, ["0 C", "5 C"]),
        ("Max Operating Temperature", 10, ["70 C", "85 C"]),
    ])

    df, mapping = grow_schema(
        table,
        reg,
        m,
        tau_new=0.4,
        tau_known=0.7,
        min_support=5,
    )

    print("\n--- CONTRAST GUARD DEBUG ---")
    print("Full mapping:", mapping)
    print("Min:", mapping.get("min operating temperature"))
    print("Max:", mapping.get("max operating temperature"))
    print("\nClassification results:")
    print(df.to_string(index=False))

    # Both attributes must be mapped before comparing them.
    assert "min operating temperature" in mapping, (
        "Min operating temperature was not mapped. "
        "Check whether it was rejected, marked ambiguous, "
        "or blocked from promotion."
    )

    assert "max operating temperature" in mapping, (
        "Max operating temperature was not mapped. "
        "Check whether it was rejected, marked ambiguous, "
        "or blocked from promotion."
    )

    # They must NOT map to the same canonical attribute.
    assert (
        mapping["min operating temperature"]
        != mapping["max operating temperature"]
    ), "Contrast guard failed: MIN and MAX were merged."

def _vec_embed(vecs, seed_vec):
    far = np.array([0, 0, 0, 1.0], dtype=np.float32)
    def emb(texts):
        out = []
        for t in texts:
            key = t.split(":")[0].strip().lower()
            out.append(np.array(vecs.get(key, seed_vec if key in SEED_KEYS else far), dtype=np.float32))
        return np.array(out)
    return emb

from app.schema_harmonization.seed_schema import SEED_ATTRIBUTES
SEED_KEYS = {a.lower() for s in SEED_ATTRIBUTES.values() for a in s["aliases"]} | {k.lower() for k in SEED_ATTRIBUTES}

def _cos(c):
    return [c, (1 - c * c) ** 0.5, 0, 0]

class CountingJudge:
    def __init__(self, answer): self.answer, self.calls = answer, []
    def __call__(self, a, sa, b, sb):
        self.calls.append((a, b)); return self.answer

def _two_names(cos):
    vecs = {"alpha": [1, 0, 0, 0], "beta": _cos(cos)}
    reg = SchemaRegistry.from_seed(); m = AttributeMatcher(reg, _vec_embed(vecs, [0, 0, 1, 0]))
    return reg, m, inv([("Alpha", 9, ["1"]), ("Beta", 8, ["2"])])

def test_three_tiers_for_cluster_joining():
    for cos, answer, expect_calls, expect_attrs in [(0.95, 0, 0, 1), (0.78, 1, 1, 1), (0.78, 0, 1, 2), (0.78, None, 1, 2), (0.50, 1, 0, 2)]:
        reg, m, table = _two_names(cos); j = CountingJudge(answer)
        grow_schema(table, reg, m, 0.4, 0.7, min_support=1, judge=j)
        learned = [a for a in reg.attributes.values() if a["origin"] == "learned"]
        assert len(j.calls) == expect_calls and len(learned) == expect_attrs, (cos, answer, len(j.calls), len(learned))

def test_without_judge_behaviour_is_unchanged():
    reg, m, table = _two_names(0.78)
    grow_schema(table, reg, m, 0.4, 0.7, min_support=1)           # default tau_join 0.80 > 0.78 -> separate
    assert len([a for a in reg.attributes.values() if a["origin"] == "learned"]) == 2

def test_contrast_guard_vetoes_before_judge():
    vecs = {"min temp": [1, 0, 0, 0], "max temp": _cos(0.78)}
    reg = SchemaRegistry.from_seed(); m = AttributeMatcher(reg, _vec_embed(vecs, [0, 0, 1, 0]))
    j = CountingJudge(1)
    grow_schema(inv([("Min Temp", 9, ["0C"]), ("Max Temp", 8, ["70C"])]), reg, m, 0.4, 0.7, min_support=1, judge=j)
    assert j.calls == [] and len([a for a in reg.attributes.values() if a["origin"] == "learned"]) == 2

def test_ambiguous_name_goes_to_judge():
    for answer, status in [(1, "known"), (0, "promoted"), (None, "review_queue")]:
        vecs = {"merk": [0.6, 0.8, 0, 0]}
        reg = SchemaRegistry.from_seed(); m = AttributeMatcher(reg, _vec_embed(vecs, [1, 0, 0, 0]))
        j = CountingJudge(answer)
        df, mapping = grow_schema(inv([("Merk", 9, ["Corsair"])]), reg, m, 0.4, 0.7, min_support=1, judge=j)
        assert df.iloc[0]["status"] == status and len(j.calls) == 1, (answer, df.iloc[0]["status"])
        if status == "known":
            assert mapping["merk"] in reg.attributes and "merk" in reg.attributes[mapping["merk"]]["aliases"]
            assert reg.version == 1

def test_suggest_mode_never_merges_by_itself():
    reg, m, table = _two_names(0.78); j = CountingJudge(1)
    df, mapping = grow_schema(table, reg, m, 0.4, 0.7, min_support=1, judge=j, judge_mode="suggest")
    assert len([a for a in reg.attributes.values() if a["origin"] == "learned"]) == 2     # stayed separate
    r = df[df.display_name == "Beta"].iloc[0]
    assert r.suggest_kind == "merge" and r.suggest_target == "alpha" and r.reason == "llm_suggests_merge"
    reg, m, table = _two_names(0.78)
    df, _ = grow_schema(table, reg, m, 0.4, 0.7, min_support=1, judge=CountingJudge(0), judge_mode="suggest")
    assert (df.suggest_kind == "").all()

def test_suggest_mode_ambiguous_name():
    for answer, status, kind in [(1, "review_queue", "alias"), (0, "promoted", ""), (None, "review_queue", "")]:
        vecs = {"merk": [0.6, 0.8, 0, 0]}
        reg = SchemaRegistry.from_seed(); m = AttributeMatcher(reg, _vec_embed(vecs, [1, 0, 0, 0]))
        df, mapping = grow_schema(inv([("Merk", 9, ["Corsair"])]), reg, m, 0.4, 0.7, min_support=1,
                                  judge=CountingJudge(answer), judge_mode="suggest")
        r = df.iloc[0]
        assert r.status == status and r.suggest_kind == kind and reg.alias_index().get("merk") not in SEED_ATTRIBUTES, (answer, r.status)
        assert reg.version == (2 if status == "promoted" else 1)

def test_accepted_hints_are_applied():
    vecs = {"merk": [0.6, 0.8, 0, 0]}
    reg = SchemaRegistry.from_seed(); m = AttributeMatcher(reg, _vec_embed(vecs, [1, 0, 0, 0]))
    seed_attr = sorted(SEED_ATTRIBUTES)[0]
    df, mapping = grow_schema(inv([("Merk", 9, ["Corsair"])]), reg, m, 0.4, 0.7, min_support=1,
                              hints={"alias": {"merk": seed_attr}})
    assert mapping["merk"] == seed_attr and "merk" in reg.attributes[seed_attr]["aliases"]
    assert df.iloc[0].reason == "review_accept"
    reg, m, table = _two_names(0.78)                                    # merge hint beats similarity 0.78 < 0.85
    df, mapping = grow_schema(table, reg, m, 0.4, 0.7, min_support=1, hints={"merge": {"beta": "alpha"}})
    assert mapping["beta"] == mapping["alpha"] and len([a for a in reg.attributes.values() if a["origin"] == "learned"]) == 1

def test_review_file_keeps_decisions(tmp_path):
    from app.schema_harmonization.schema_review import export_review, load_hints
    reg, m, table = _two_names(0.78)
    df, _ = grow_schema(table, reg, m, 0.4, 0.7, min_support=1, judge=CountingJudge(1), judge_mode="suggest")
    path = tmp_path / "review.csv"
    n, todo = export_review(df, table, path)
    assert (n, todo) == (1, 1) and load_hints(path) == {"alias": {}, "merge": {}}
    d = pd.read_csv(path); d["decision"] = "accept"; d.to_csv(path, index=False)
    n, todo = export_review(df, table, path)                            # re-export must not wipe the decision
    assert todo == 0 and load_hints(path)["merge"] == {"beta": "alpha"}

def test_excluded_names_are_never_review_suggestions(tmp_path):
    from app.schema_harmonization.schema_review import export_review
    reg = SchemaRegistry.from_seed(); m = AttributeMatcher(reg, fake_embed)
    table = inv([("Pakketpost", 50, ["€ 0,-"]), ("Latency", 6, ["CL16"])])
    df, _ = grow_schema(table, reg, m, 0.4, 0.7, 5, judge=CountingJudge(1), judge_mode="suggest")
    assert (df["suggest_kind"] == "").all() and df["suggest_kind"].notna().all()
    assert export_review(df, table, tmp_path / "r.csv") == (0, 0)

def test_conflicts_digit_and_size_variants():
    assert conflicts("cache l2", "cache l3") and conflicts("large form factor", "small form factor")
    assert conflicts("ddr3 speed", "ddr4 speed") and not conflicts("hot swap", "hotswap")

def test_value_normalizer():
    from app.schema_harmonization.value_normalizer import normalize_value as nv
    assert nv("8 GB")["value"] == 8 and nv("8000 MB")["value"] == 8 and nv("8 GB")["unit"] == "GB"
    assert nv("2 x 4 GB")["value"] == 8 and nv("1 TB")["value"] == 1000
    assert nv("3.2GHz")["value"] == 3200 and nv("3200 MHz")["value"] == 3200
    assert nv("1.631,0 µs")["value"] == 1.631 and nv("4,17ms")["value"] == 4.17
    assert nv("2 lb")["unit"] == "g" and nv("1 year")["value"] == 12
    assert nv("7200RPM")["family"] == "rotation"
    for bad in ["[email\xa0protected]", "N/A", "-", "", None]:
        assert nv(bad)["status"] == "missing"
    assert nv("Quad-Core")["status"] == "text" and nv("Quad-Core")["value"] == "quad-core"
    assert nv("12 widgets")["status"] == "text"
