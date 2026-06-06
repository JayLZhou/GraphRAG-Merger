"""Semantic bridge discovery between two indexes.

A *bridge* is a candidate correspondence between an entity in the smaller index
and an entity in the larger index. For each small-index entity we score its best
matches in the large index, combining several complementary signals so no single
noisy signal dominates:

- **normalized name similarity** (token-aware, handles initials);
- **alias overlap** (token Jaccard over name+aliases);
- **type compatibility** (1.0 match / 0.0 known-mismatch / 0.5 unknown);
- **description embedding similarity** (cosine, only when both embeddings exist);
- **neighbor overlap** (Jaccard of neighbor *names*, since ids differ across indexes);
- **temporal compatibility** (0.0 when validity intervals are disjoint).

Weights are renormalized over the signals actually available for a pair, so
absent embeddings/timestamps degrade gracefully rather than dragging the score
down.

**Blocking.** A brute-force ``N_small x N_large`` comparison is wasteful. We
build an inverted index from blocking keys (name tokens of length >= 3 plus each
name's first character) to large-index entities, and only score pairs that share
a key. This is what makes discovery ``~O(N_small * b)`` rather than quadratic;
``BridgeResult.comparisons`` records how many pairs were actually scored.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

from . import util
from .schema import (
    BridgeCandidate,
    BridgeConfidence,
    BridgeResult,
    Entity,
    MergeConfig,
    SemanticIndex,
)


def _blocking_keys(entity: Entity) -> Set[str]:
    """Keys under which an entity is indexed/probed for candidate matching."""
    keys: Set[str] = set()
    for tok in util.alias_token_set(entity):
        if len(tok) >= 3:
            keys.add(tok)
        keys.add(f"^{tok[0]}")  # first-character bucket (catches initials)
    return keys


def _type_compat(a: Entity, b: Entity) -> float:
    if a.type is None or b.type is None:
        return 0.5
    return 1.0 if a.type.strip().lower() == b.type.strip().lower() else 0.0


def _neighbor_names(index: SemanticIndex, entity_id: str) -> Set[str]:
    names: Set[str] = set()
    for nb in index.neighbors(entity_id):
        ent = index.entity(nb)
        if ent:
            names.add(util.normalize_name(ent.name))
    return names


def _temporal_compat(a: Entity, b: Entity) -> float:
    return 1.0 if util.intervals_overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to) else 0.0


def score_pair(
    a: Entity,
    b: Entity,
    index_a: SemanticIndex,
    index_b: SemanticIndex,
    config: MergeConfig,
) -> BridgeCandidate:
    """Score a single candidate pair, recording per-signal features."""
    features: Dict[str, float] = {}
    weights: Dict[str, float] = {}

    features["name"] = util.best_label_similarity(a, b)
    weights["name"] = config.w_name

    features["alias"] = util.alias_overlap(a, b)
    weights["alias"] = config.w_alias

    features["type"] = _type_compat(a, b)
    weights["type"] = config.w_type

    if config.use_embeddings and a.embedding and b.embedding:
        features["embedding"] = util.cosine(a.embedding, b.embedding)
        weights["embedding"] = config.w_embedding

    na, nb = _neighbor_names(index_a, a.id), _neighbor_names(index_b, b.id)
    if na or nb:
        features["neighbor"] = util.jaccard(na, nb)
        weights["neighbor"] = config.w_neighbor

    if any([a.valid_from, a.valid_to, b.valid_from, b.valid_to]):
        features["temporal"] = _temporal_compat(a, b)
        weights["temporal"] = config.w_temporal

    total_w = sum(weights.values()) or 1.0
    score = sum(features[k] * weights[k] for k in weights) / total_w

    return BridgeCandidate(
        source_id=a.id,
        target_id=b.id,
        score=score,
        confidence=BridgeConfidence.LOW,
        features=features,
    )


def discover_entity_bridges(
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    config: MergeConfig,
) -> BridgeResult:
    """Discover candidate entity bridges from ``index_small`` into ``index_large``.

    Returns candidates grouped per source entity (best first), plus the number
    of pairs scored. Embedding and temporal signals are used only when present.
    """
    # Build the blocking inverted index over the large side.
    block_index: Dict[str, List[str]] = defaultdict(list)
    for ent in index_large.entities.values():
        for key in _blocking_keys(ent):
            block_index[key].append(ent.id)

    result = BridgeResult()
    for src in index_small.entities.values():
        # Gather large-side candidates sharing at least one blocking key.
        candidate_ids: Set[str] = set()
        for key in _blocking_keys(src):
            candidate_ids.update(block_index.get(key, ()))

        scored: List[BridgeCandidate] = []
        for tid in candidate_ids:
            tgt = index_large.entities[tid]
            result.comparisons += 1
            cand = score_pair(src, tgt, index_small, index_large, config)
            if cand.score >= config.candidate_threshold:
                scored.append(cand)

        scored.sort(key=lambda c: c.score, reverse=True)
        if scored:
            result.by_source[src.id] = scored
            result.candidates.extend(scored)

    return result
