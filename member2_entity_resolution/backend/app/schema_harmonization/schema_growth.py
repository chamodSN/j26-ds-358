"""Self-extending schema (Novelty 2).

For every attribute name found in the data (most frequent first):
  0. names whose VALUES are prices (currency symbols) are EXCLUDED: shipping/price fields describe
     the offer, not the product (language-independent; a small name list is only a secondary filter)
  1. exact alias of a canonical attribute       -> KNOWN (deterministic, similarity 1.0)
  2. else nearest canonical attribute by SBERT   -> KNOWN / AMBIGUOUS / NEW  (two thresholds)
  3. NEW names are grouped into PENDING candidates: a name joins a candidate if its similarity to the
     candidate CENTROID >= tau_join and no CONTRAST GUARD fires (min/max, read/write, different
     numbers ... are different attributes)
  4. a candidate is PROMOTED to a new canonical attribute only if it has enough SUPPORT
     (>= min_support records); it is tagged with a ROLE (spec | identifier | descriptive)
  5. AMBIGUOUS names are never added automatically; they go to a review queue
All promotions of one run form ONE new schema version; every change is in the changelog."""
import re

import numpy as np
import pandas as pd

from app.schema_harmonization.attribute_inventory import normalise_name, parse_kvp
from app.schema_harmonization.attribute_matcher import AMBIGUOUS, KNOWN, NEW, classify
from app.schema_harmonization.value_types import NON_SPEC_TYPES, attribute_role, cluster_value_type

CONTRAST_SETS = [
    {"min", "minimum", "max", "maximum"},
    {"read", "reads", "lees", "leestijd", "write", "writes", "schrijf", "schrijftijd", "opentijd", "responstijd"},
    {"input", "output"}, {"internal", "external"}, {"upper", "lower"},
    {"front", "rear", "back", "side"}, {"width", "height", "depth"}, {"upload", "download"},
    {"small", "medium", "large"}, {"desktop", "graphics", "workstation"}, {"from", "on"},
]

COMMERCE_NAME_TERMS = {"shipping", "delivery", "return policy", "payment", "postage", "price", "total price",
                       "pakketpost", "briefpost", "brievenbuspost", "brievenpost", "verzending", "ideal",
                       "productprijs", "totaal", "opsturen", "bezorging", "bezorgkosten", "verzendkosten",
                       "thuisbezorgd"}   # SECONDARY filter; the value test is the primary one


def is_commerce_name(name_norm):
    return any(re.search(rf"\b{re.escape(t)}\b", name_norm) for t in COMMERCE_NAME_TERMS)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_") or "attribute"


def conflicts(name_a, name_b):
    """True if two names differ by tokens that mark DIFFERENT attributes
    (min vs max, read vs write, q 1 vs q 8, 2.5 vs 3.5 ...). SBERT scores such pairs as near-identical."""
    ta, tb = set(name_a.split()), set(name_b.split())
    da, db = ta - tb, tb - ta
    for x in da:
        for y in db:
            if x[0].isdigit() and y[0].isdigit():
                return True
            sx, sy = x.strip("0123456789."), y.strip("0123456789.")
            if sx and sx == sy and x != y and (x != sx or y != sy):   # l2 vs l3, ddr3 vs ddr4, q1 vs q8
                return True
            if any(x in s and y in s for s in CONTRAST_SETS):
                return True
    return False


def _seed_label(registry, attr):
    spec = registry.attributes[attr]
    others = [a for a in spec["aliases"] if a != attr][:4]
    return (f"{attr} (also called: {', '.join(others)})" if others else attr), spec.get("examples", [])[:3]


def grow_schema(inventory, registry, matcher, tau_new, tau_known, min_support=5, tau_join=None,
                judge=None, tau_join_lo=0.70, judge_mode="decide", hints=None):
    """Returns (decisions DataFrame, mapping {name_norm: attr_id}). Mutates `registry`.
    judge_mode="decide":  the judge's MATCH is acted on (measured: only ~64% of its MATCHes are right)
    judge_mode="suggest": the judge may only SEPARATE (NON_MATCH) or SUGGEST (MATCH -> human review queue);
                          accepted suggestions come back in as `hints` on the next run."""
    if tau_join is None:
        tau_join = 0.85 if judge is not None else max(tau_known, 0.80)
    best_id, best_sim, embs = matcher.score(list(inventory["display_name"]), list(inventory["samples"]))
    alias_idx = registry.alias_index()
    hints = hints or {}
    alias_hints, merge_hints = hints.get("alias", {}), hints.get("merge", {})   # human-approved review decisions

    rows, pending = [], []      # pending cluster: dict(members=[row idx], names=[...], sum=vector, support=int)
    for i, r in enumerate(inventory.itertuples()):
        vt = cluster_value_type(list(r.samples), [r.name_norm])
        if vt in NON_SPEC_TYPES or is_commerce_name(r.name_norm):
            rows.append(dict(name_norm=r.name_norm, display_name=r.display_name, count=int(r.count),
                             kind="excluded", attr_id="", nearest="", sim=0.0,
                             reason="currency_values" if vt in NON_SPEC_TYPES else "commerce_name",
                             status="excluded", note=vt, suggest_kind="", suggest_target=""))
            continue
        suggest_kind, suggest_target = "", ""
        if r.name_norm in alias_idx:
            kind, attr, sim, why = KNOWN, alias_idx[r.name_norm], 1.0, "alias"
        elif alias_hints.get(r.name_norm) in registry.attributes:
            kind, attr, sim, why = KNOWN, alias_hints[r.name_norm], 1.0, "review_accept"
        else:
            kind, attr, sim, why = classify(best_sim[i], tau_new, tau_known), best_id[i], float(best_sim[i]), "embedding"
            if kind == AMBIGUOUS and judge is not None:      # middle band -> LLM: same as the nearest canonical attribute?
                label, ex = _seed_label(registry, attr)
                v = judge(r.display_name, r.samples, label, ex)
                if v == 1 and judge_mode == "decide":
                    kind, why = KNOWN, "llm_same_as_seed"
                elif v == 1:                                     # suggest: stays AMBIGUOUS -> review queue
                    suggest_kind, suggest_target, why = "alias", attr, "llm_suggests_alias"
                elif v == 0:
                    kind, why = NEW, "llm_not_seed"       # genuinely different -> candidate NEW attribute

        if kind == KNOWN:
            registry.add_alias(attr, r.name_norm, support=r.count)
            status = "known"
        elif kind == AMBIGUOUS:
            status = "review_queue"
        else:                                           # NEW -> join / create a pending candidate
            target, target_sim = None, -1.0
            for p in pending:
                if any(conflicts(r.name_norm, n) for n in p["names"]):
                    continue
                s = float(p["sum"] @ embs[i] / np.linalg.norm(p["sum"]))
                if s > target_sim:
                    target, target_sim = p, s
            join = target is not None and target_sim >= tau_join
            partner = merge_hints.get(r.name_norm)
            forced = next((p for p in pending if partner and partner in p["names"]), None)
            if forced is not None:                                   # a human approved this merge
                target, join, why = forced, True, "review_accept"
            elif not join and judge is not None and target is not None and target_sim >= tau_join_lo:
                rep = inventory.iloc[target["members"][0]]            # most frequent member represents the cluster
                v = judge(r.display_name, r.samples, rep["display_name"], rep["samples"])
                if judge_mode == "decide":
                    join = v == 1
                    why = "llm_join" if join else "llm_separate"
                elif v == 1:                                         # suggest: stays separate, human decides
                    suggest_kind, suggest_target, why = "merge", rep["name_norm"], "llm_suggests_merge"
                else:
                    why = "llm_separate"
            if join:
                p = target
            else:
                p = dict(members=[], names=[], sum=np.zeros_like(embs[i]), support=0)
                pending.append(p)
            p["members"].append(i)
            p["names"].append(r.name_norm)
            p["sum"] = p["sum"] + embs[i]
            p["support"] += int(r.count)
            status = "pending"
        rows.append(dict(name_norm=r.name_norm, display_name=r.display_name, count=int(r.count),
                         kind=kind, attr_id=attr if kind == KNOWN else "", nearest=attr,
                         sim=round(sim, 3), reason=why, status=status, note="",
                         suggest_kind=suggest_kind, suggest_target=suggest_target))

    df = pd.DataFrame(rows)

    # ---- promotion: support gate, then role tag ----
    for p in pending:
        member_rows = df.iloc[p["members"]]
        samples = [s for i in p["members"] for s in inventory.iloc[i]["samples"]]
        vtype = cluster_value_type(samples, list(member_rows["name_norm"]))
        idx = member_rows.index
        if p["support"] < min_support:
            df.loc[idx, ["status", "note"]] = ["pending_low_support", vtype]
        else:
            role = attribute_role(list(member_rows["name_norm"]), vtype)
            top = member_rows.sort_values("count", ascending=False)
            attr_id = registry.add_attribute(
                slug(top.iloc[0]["display_name"]),
                aliases=list(member_rows["name_norm"]), examples=samples[:5], support=p["support"],
                reason=f"{len(member_rows)} name(s), support {p['support']} >= {min_support}, values look like "
                       f"'{vtype}', no canonical attribute above similarity {tau_new}", role=role)
            df.loc[idx, ["status", "attr_id", "note"]] = ["promoted", attr_id, role]
    registry.commit()

    mapping = {r.name_norm: r.attr_id for r in df.itertuples() if r.status in ("known", "promoted")}
    return df, mapping


def harmonize_record(kvp, mapping):
    """Raw attributes of one listing -> canonical attributes. Unmapped names are kept, never dropped."""
    out, unmapped = {}, {}
    for k, v in parse_kvp(kvp).items():
        attr = mapping.get(normalise_name(k))
        if attr:
            out.setdefault(attr, v)
        else:
            unmapped[k] = v
    return dict(canonical=out, unmapped=unmapped)


def coverage(kvp_series, mapping):
    """How many listings get canonical attributes under this mapping? (coverage is NOT accuracy)"""
    n_kv = n_hit = total = 0
    for raw in kvp_series:
        if not parse_kvp(raw):
            continue
        n_kv += 1
        k = len(harmonize_record(raw, mapping)["canonical"])
        n_hit += k > 0
        total += k
    return dict(listings_with_attributes=n_kv,
                share_with_canonical=n_hit / max(n_kv, 1),
                mean_canonical_per_listing=total / max(n_kv, 1))