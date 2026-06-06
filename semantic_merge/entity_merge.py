"""Conflict-aware entity fusion.

Given pruned bridges, decide which entities actually fuse and build the merged
entity set plus a mapping from old entity ids to canonical ids (consumed by
``edge_reconcile``).

Decision policy:
  * **high-confidence** bridges fuse the two entities into one canonical entity;
  * **low-confidence** pairs stay separate (no fusion);
  * **ambiguous** pairs are *not* fused but recorded as ambiguity / conflict
    sets so the information is preserved.

Fusion must be loss-less on evidence: union ``aliases``, ``text_unit_ids`` and
``provenance``; keep both descriptions (or merge them) without dropping either;
reconcile ``valid_from``/``valid_to`` to the widest consistent interval. When a
high-confidence bridge nonetheless carries a hard conflict (incompatible type),
prefer preserving a conflict set over forcing a fuse.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schema import (
    ConflictSet,
    Entity,
    MergeConfig,
    PruneResult,
    SemanticIndex,
)


def merge_entities(
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    pruned: PruneResult,
    config: MergeConfig,
) -> Tuple[Dict[str, Entity], Dict[str, str], List[ConflictSet]]:
    """Fuse entities according to pruned bridges.

    Returns:
      * ``merged_entities`` — canonical entity id -> fused :class:`Entity`;
      * ``id_map``          — original entity id -> canonical entity id (for
        every entity in both indexes, fused or not);
      * ``conflicts``       — conflict/ambiguity records preserved during fusion.
    """
    raise NotImplementedError(
        "TODO(codex task 1): implement conflict-aware entity fusion + id remap"
    )
