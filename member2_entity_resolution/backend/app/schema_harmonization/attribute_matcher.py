"""Decide, for an incoming attribute (name + sample values), whether it is
  KNOWN      - same meaning as an existing canonical attribute,
  NEW        - not covered by the schema,
  AMBIGUOUS  - in between: not added automatically, goes to a review queue.

The decision uses ONE number: the cosine similarity to the nearest canonical attribute,
compared with two thresholds (tau_new < tau_known) - the same two-threshold idea as Novelty 1."""
import numpy as np

KNOWN, NEW, AMBIGUOUS = "known", "new", "ambiguous"


def attribute_text(name, samples, use_values=True):
    samples = [s for s in (samples or []) if s][:3]
    return f"{name}: {'; '.join(samples)}" if (use_values and samples) else str(name)


def classify(sim, tau_new, tau_known):
    if sim >= tau_known:
        return KNOWN
    if sim < tau_new:
        return NEW
    return AMBIGUOUS


class AttributeMatcher:
    def __init__(self, registry, embed_fn, use_values=True):
        self.registry, self.embed_fn, self.use_values = registry, embed_fn, use_values
        self.refresh()

    def refresh(self):
        """(Re)build one embedding per canonical alias. Call after the schema changed."""
        rows = self.registry.members()
        self.member_attr = np.array([r[0] for r in rows])
        texts = [attribute_text(alias, ex, self.use_values) for _, alias, ex in rows]
        self.member_emb = np.asarray(self.embed_fn(texts), dtype=np.float32)
        self.attr_ids = list(self.registry.attributes)

    def embed(self, names, samples_list):
        texts = [attribute_text(n, s, self.use_values) for n, s in zip(names, samples_list)]
        return np.asarray(self.embed_fn(texts), dtype=np.float32)

    def score_embeddings(self, q):
        """best canonical attribute and similarity for each query embedding (max over its aliases)."""
        sims = q @ self.member_emb.T                       # (n_queries, n_members)
        best_sim = np.full(len(q), -1.0)
        best_id = np.array([""] * len(q), dtype=object)
        for attr_id in self.attr_ids:
            cols = np.where(self.member_attr == attr_id)[0]
            s = sims[:, cols].max(axis=1)
            better = s > best_sim
            best_sim[better], best_id[better] = s[better], attr_id
        return best_id, best_sim

    def score(self, names, samples_list):
        q = self.embed(names, samples_list)
        best_id, best_sim = self.score_embeddings(q)
        return best_id, best_sim, q