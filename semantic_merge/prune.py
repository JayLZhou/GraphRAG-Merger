"""Robust pruning of bridge candidates.

Bridge discovery is deliberately high-recall; pruning trims it to a robust,
bounded set without discarding genuine uncertainty. The guiding principle is
*preserve ambiguity and conflict* — collapsing them silently is exactly the
failure mode a naive merge exhibits.

Rules:
  1. keep at most ``M = config.max_candidates_per_entity`` candidates per
     source entity (highest score first);
  2. filter candidates that are type- or time-*incompatible* (hard violations);
  3. preserve ambiguous candidates (score in the ambiguous band, or near-ties
     among the top candidates) as :class:`~semantic_merge.schema.AmbiguitySet`;
  4. preserve conflict candidates (e.g. same name, incompatible type/time) so
     downstream stages can record them rather than overwrite evidence.
"""

from __future__ import annotations

from .schema import BridgeResult, MergeConfig, PruneResult, SemanticIndex


def robust_semantic_prune(
    bridges: BridgeResult,
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    config: MergeConfig,
) -> PruneResult:
    """Prune ``bridges`` into retained / ambiguous / conflict sets.

    Returns a :class:`~semantic_merge.schema.PruneResult` with:
      * ``retained``   — bounded, compatible candidates eligible for fusion;
      * ``ambiguities`` — preserved ambiguity sets (one per uncertain source);
      * ``conflicts``  — candidates flagged as conflicting rather than droppable.

    Must never silently delete a candidate that represents a genuine conflict.
    """
    raise NotImplementedError(
        "TODO(codex task 1): implement RobustSemanticPrune (bound M, preserve ambiguity/conflict)"
    )
