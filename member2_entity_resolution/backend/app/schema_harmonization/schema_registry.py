"""The canonical schema as a small versioned JSON document.
It starts as the hand-written seed (version 1) and GROWS: every change bumps the version
and is written to a changelog, so any past decision can be explained and audited."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from app.schema_harmonization.attribute_inventory import normalise_name
from app.schema_harmonization.seed_schema import SEED_ATTRIBUTES


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SchemaRegistry:
    def __init__(self, data: dict):
        self.data = data
        self._uncommitted = False

    # ---------------- creation / persistence ----------------
    @classmethod
    def from_seed(cls):
        attrs = {}
        for attr_id, spec in SEED_ATTRIBUTES.items():
            attrs[attr_id] = dict(aliases=[normalise_name(a) for a in spec["aliases"]],
                                  examples=list(spec["examples"]), origin="seed",
                                  support=0, added_in_version=1)
        return cls(dict(version=1, attributes=attrs, changelog=[]))

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def copy(self):
        return SchemaRegistry(copy.deepcopy(self.data))

    # ---------------- read access ----------------
    @property
    def version(self):
        return self.data["version"]

    @property
    def attributes(self):
        return self.data["attributes"]

    @property
    def changelog(self):
        return self.data["changelog"]

    def alias_index(self) -> dict:
        return {a: attr_id for attr_id, spec in self.attributes.items() for a in spec["aliases"]}

    def members(self):
        """(attr_id, alias, examples) rows - one embedding is built per row."""
        return [(attr_id, alias, spec["examples"])
                for attr_id, spec in self.attributes.items() for alias in spec["aliases"]]

    # ---------------- changes (all versioned) ----------------
    def add_alias(self, attr_id, alias, support=0):
        """A known attribute was seen under a new name: remember it (schema version unchanged)."""
        alias = normalise_name(alias)
        spec = self.attributes[attr_id]
        if alias not in spec["aliases"]:
            spec["aliases"].append(alias)
            self.changelog.append(dict(at=_now(), version=self.version, action="alias_added",
                                       attribute=attr_id, alias=alias))
        spec["support"] += int(support)

    def add_attribute(self, attr_id, aliases, examples, support, reason, role="spec"):
        """PROMOTION: a new canonical attribute. All promotions of one growth run belong to ONE new
        schema version; call commit() when the run is finished."""
        base, n = attr_id, 2
        while attr_id in self.attributes:
            attr_id, n = f"{base}_{n}", n + 1
        target = self.version + 1
        self.attributes[attr_id] = dict(aliases=sorted({normalise_name(a) for a in aliases}),
                                        examples=list(examples)[:5], origin="learned", role=role,
                                        support=int(support), added_in_version=target)
        self.changelog.append(dict(at=_now(), version=target, action="attribute_added",
                                   attribute=attr_id, aliases=self.attributes[attr_id]["aliases"],
                                   support=int(support), reason=reason))
        self._uncommitted = True
        return attr_id

    def commit(self):
        """Close a growth run: the version goes up by exactly one if anything was added."""
        if self._uncommitted:
            self.data["version"] += 1
            self._uncommitted = False
        return self.version