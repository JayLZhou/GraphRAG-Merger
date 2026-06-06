"""Semantic bridge discovery between two indexes.

A *bridge* is a candidate correspondence between an entity in the smaller index
and an entity in the larger index. Discovery is the asymmetric, forward step of
the merge: for each entity in the small index we score its best matches in the
large index, combining several complementary signals so that no single noisy
signal dominates.

Signals (each normalized to ``[0, 1]``, combined with the weights in
:class:`~semantic_merge.schema.MergeConfig`):

- **normalized name similarity** — case/whitespace/punctuation-folded string
  similarity (e.g. token-set ratio) between canonical names.
- **alias overlap** — Jaccard overlap of the two entities' alias sets.
- **type compatibility** — 1.0 if types match / are compatible, 0 if they are
  known-incompatible, neutral if unknown.
- **description embedding similarity** — cosine similarity of description
  embeddings, *only when embeddings are present* on both entities.
- **neighbor overlap** — overlap of the two entities' already-merged
  neighborhoods (structural evidence).
- **temporal compatibility** — penalize pairs whose validity intervals cannot
  co-refer, when timestamps are available.

Blocking: a brute-force ``N_small x N_large`` comparison is wasteful. Use a
cheap blocking key (e.g. normalized-name prefix / type bucket) to only score
plausibly-related pairs; this is what makes the binary merge cost
``O(N_small * log N_large)`` rather than quadratic (see ``docs/theory.md``).
"""

from __future__ import annotations

from .schema import BridgeResult, MergeConfig, SemanticIndex


def discover_entity_bridges(
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    config: MergeConfig,
) -> BridgeResult:
    """Discover candidate entity bridges from ``index_small`` into ``index_large``.

    Returns a :class:`~semantic_merge.schema.BridgeResult` whose candidates are
    grouped per source entity, best first. Embedding and temporal signals are
    used only when the relevant fields are populated; the scorer must degrade
    gracefully when they are absent.

    Implementation notes:
      * apply blocking before scoring to avoid the quadratic comparison;
      * record per-signal scores in ``BridgeCandidate.features`` for auditability;
      * drop pairs below ``config.candidate_threshold``.
    """
    raise NotImplementedError(
        "TODO(codex task 1): implement multi-signal bridge discovery with blocking"
    )
