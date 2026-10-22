"""Online entity resolution + schema harmonization for a SMALL batch of listings (API / demo).

Same tiers as the evaluated Strategy C:
  1 embed titles (SBERT, normalised)        2 block: top-k nearest listings from OTHER sources
  3 rules verdict + cosine -> cascade_c     4 LLM only for routed pairs (per-request budget)
  5 union-find -> entity clusters           6 map attribute names to the FROZEN schema, normalise values
Blocking here is exact search (batches <= 300 listings); the evaluated system used FAISS for large corpora."""
import json
import os
import re
from pathlib import Path

import numpy as np

from app.entity_resolution.router_v2 import cascade_c
ACCEPT, REJECT, UNDECIDED = 1, 0, -1
from app.entity_resolution.rules import verdict as _rules_verdict
from app.schema_harmonization.text_embedder import embed_texts
from app.schema_harmonization.value_normalizer import normalize_value

ROOT = Path(__file__).resolve().parents[3]            # member2_entity_resolution  (/srv/member2 in Docker)
SCHEMA_PATH = Path(os.getenv("ER_SCHEMA_PATH", ROOT / "schemas" / "canonical_schema_v2_frozen.json"))
LO = float(os.getenv("ER_LO", "0.40"))
HI = float(os.getenv("ER_HI", "0.88"))
TOP_K = int(os.getenv("ER_TOP_K", "5"))
MAX_LLM_CALLS = int(os.getenv("ER_MAX_LLM_CALLS", "40"))
_SCHEMA = None


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def load_schema(path=SCHEMA_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    attrs = data.get("attributes", data)
    if isinstance(attrs, list):
        attrs = {a["key"]: a for a in attrs}
    alias = {}
    for key, spec in attrs.items():
        alias[norm_name(key)] = key
        for a in spec.get("aliases", []):
            alias[norm_name(a)] = key
    return dict(version=data.get("version"), n_attributes=len(attrs), alias=alias)


def schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = load_schema()
    return _SCHEMA


def rule_verdict(a, b):
    """-> (code, reason).  code: 1 accept / 0 reject / -1 undecided."""
    v, reason = _rules_verdict(a, b), ""
    if isinstance(v, tuple):
        v, reason = v[0], (str(v[1]) if len(v) > 1 else "")
    if isinstance(v, str):
        return {"accept": ACCEPT, "reject": REJECT}.get(v.lower(), UNDECIDED), reason
    return (UNDECIDED if v is None else int(v)), reason


def candidate_pairs(E, sources, k=TOP_K):
    """Each listing proposes its k nearest listings from OTHER sources."""
    sim = E @ E.T
    pairs = set()
    for i in range(len(E)):
        taken = 0
        for j in np.argsort(-sim[i]):
            if j == i or sources[j] == sources[i]:
                continue
            pairs.add((int(min(i, j)), int(max(i, j))))
            taken += 1
            if taken >= k:
                break
    return sorted(pairs), sim


def harmonize(listing):
    """-> ({canonical_attr: normalised value}, [names not in the schema])"""
    alias, mapped, unmapped = schema()["alias"], {}, []
    for name, raw in (listing.get("attributes") or {}).items():
        attr = alias.get(norm_name(name))
        if attr is None:
            unmapped.append(name)
            continue
        nv = normalize_value(raw)
        if nv["status"] != "missing":
            mapped.setdefault(attr, nv)
    return mapped, unmapped


def merge_cluster(harmonized):
    canon = {}
    for attr in sorted({a for h in harmonized for a in h}):
        vals = [h[attr] for h in harmonized if attr in h]
        canon[attr] = dict(value=vals[0]["value"], unit=vals[0]["unit"], status=vals[0]["status"],
                           n_sources=len(vals), conflict=len({(v["unit"], str(v["value"])) for v in vals}) > 1)
    return canon


def resolve(listings, use_llm=True, judge=None):
    """judge(left_title, right_title) -> 1 / 0 / None.  Default: the real LLM client (budgeted per request)."""
    n = len(listings)
    titles, sources = [l["title"] for l in listings], [l.get("source", "unknown") for l in listings]
    E = np.asarray(embed_texts(titles), dtype=np.float32)
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-12)
    pairs, sim = candidate_pairs(E, sources)

    decisions, parent = [], list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    llm_sent, client = 0, None
    if pairs:
        cos = np.array([sim[i, j] for i, j in pairs])
        rv = [rule_verdict(titles[i], titles[j]) for i, j in pairs]
        verd = np.array([x[0] for x in rv])
        pred, routed = cascade_c(cos, verd, np.ones(len(pairs), dtype=int), LO, HI)
        if use_llm and routed.any() and judge is None:
            from app.entity_resolution.llm_client import LLMClient
            from app.entity_resolution.llm_matcher import judge_pair
            client = LLMClient(max_calls=MAX_LLM_CALLS)
            judge = lambda a, b: judge_pair(client, a, b)[0]
        for k, (i, j) in enumerate(pairs):
            note = ""
            if pred[k]:
                tier, ans = "rule_accept", 1
            elif routed[k]:
                tier = "llm"
                if not use_llm:
                    ans, note = None, "llm_skipped"
                else:
                    llm_sent += 1
                    try:
                        ans = judge(titles[i], titles[j])
                    except Exception as e:                     # budget exhausted, network error ...
                        ans, note = None, type(e).__name__
            else:
                tier, ans = "auto_reject", 0
            if ans == 1:
                parent[find(i)] = find(j)
            decisions.append(dict(left=listings[i]["id"], right=listings[j]["id"], cosine=round(float(cos[k]), 3),
                                  rule={1: "accept", 0: "reject", -1: "undecided"}[int(verd[k])], rule_reason=rv[k][1], tier=tier,
                                  decision="match" if ans == 1 else "non_match" if ans == 0 else "unresolved", note=note))

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    clusters = []
    for e, idxs in enumerate(sorted(groups.values(), key=lambda g: g[0]), 1):
        hs, members = [], []
        for i in idxs:
            h, un = harmonize(listings[i])
            hs.append(h)
            members.append(dict(id=listings[i]["id"], source=sources[i], title=titles[i], unmapped_attributes=un))
        clusters.append(dict(entity_id=f"e{e}", members=members, canonical=merge_cluster(hs)))

    tiers = [d["tier"] for d in decisions]
    return dict(schema_version=schema()["version"], clusters=clusters, decisions=decisions,
                stats=dict(listings=n, candidate_pairs=len(pairs), rule_accept=tiers.count("rule_accept"),
                           auto_reject=tiers.count("auto_reject"), llm_routed=tiers.count("llm"),
                           llm_pairs_sent=llm_sent, llm_network_calls=getattr(client, "network_calls", 0),
                           unresolved=sum(d["decision"] == "unresolved" for d in decisions),
                           llm_rate=round(tiers.count("llm") / max(len(pairs), 1), 3), lo=LO, hi=HI))