"""Robust pruning of bridge candidates.

Bridge discovery is deliberately high-recall; pruning trims it to a robust,
bounded set without discarding genuine uncertainty. The guiding principle is
*preserve ambiguity and conflict* — collapsing them silently is exactly the
failure mode a naive merge exhibits.

Rules:
  1. keep at most ``M = config.max_candidates_per_entity`` candidates per source;
  2. route hard type/time-*incompatible* candidates: if they nonetheless look
     like the same entity (high name similarity) they are **conflicts**
     (same-name-different-entity / temporal), otherwise they are dropped;
  3. among compatible candidates, a single clear winner above the high-confidence
     threshold is **retained** for fusion;
  4. compatible candidates that are merely plausible (ambiguous band), or a top
     pair too close to separate, are **preserved** as ambiguity sets — never
     silently fused or dropped.
"""

from __future__ import annotations

from typing import List

from .schema import (
    AmbiguitySet,
    BridgeCandidate,
    BridgeConfidence,
    BridgeResult,
    ConflictKind,
    MergeConfig,
    PruneResult,
    SemanticIndex,
)


def _is_hard_incompatible(cand: BridgeCandidate) -> bool:
    """Type known-mismatch or disjoint validity intervals."""
    return cand.features.get("type", 0.5) == 0.0 or cand.features.get("temporal", 1.0) == 0.0


def robust_semantic_prune(
    bridges: BridgeResult,
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    config: MergeConfig,
) -> PruneResult:
    """Prune ``bridges`` into retained / ambiguous / conflict sets."""
    result = PruneResult()

    for source_id, cands in bridges.by_source.items():
        top = cands[: config.max_candidates_per_entity]

        viable: List[BridgeCandidate] = []
        for c in top:
            if _is_hard_incompatible(c):
                # Same name but incompatible type/time -> a real conflict to keep.
                # (entity_merge re-derives the ConflictKind from these features.)
                if c.features.get("name", 0.0) >= config.ambiguous_threshold:
                    c.confidence = BridgeConfidence.LOW
                    result.conflicts.append(c)
                # otherwise: incompatible and not similar -> genuinely drop it.
                continue
            viable.append(c)

        if not viable:
            continue

        best = viable[0]
        runner = viable[1] if len(viable) > 1 else None
        close_call = runner is not None and runner.score >= config.ambiguous_threshold and (
            best.score - runner.score
        ) < config.ambiguous_margin

        if best.score >= config.high_confidence_threshold and not close_call:
            best.confidence = BridgeConfidence.HIGH
            result.retained.append(best)
        elif best.score >= config.ambiguous_threshold:
            contenders = [c for c in viable if c.score >= config.ambiguous_threshold]
            for c in contenders:
                c.confidence = BridgeConfidence.AMBIGUOUS
            result.ambiguities.append(
                AmbiguitySet(
                    source_id=source_id,
                    candidates=contenders,
                    reason=ConflictKind.AMBIGUOUS_BRIDGE,
                )
            )
        # else: best below ambiguous band -> low confidence, no action.

    return result
