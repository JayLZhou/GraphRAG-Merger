"""Affected-region detection.

A merge only perturbs part of the graph. The *affected region* is the set of
communities whose membership, internal edges, or boundary changed as a result
of entity fusion and edge reconciliation. Repair (summary regeneration,
reclustering) should touch only this region — that locality is what makes
incremental merging cheaper than a full rebuild (see ``docs/theory.md``,
"affected region completeness").

A community is affected if any of:
  * one of its entities was fused, split, or remapped;
  * an internal or boundary relationship was added, versioned, or flagged
    conflicting;
  * its entity/edge membership count changed.

Completeness requirement: every community that a full rebuild would change must
be reported. Over-reporting is safe (wasteful); under-reporting is a
correctness bug.
"""

from __future__ import annotations

from typing import Dict, List, Set

from .schema import ConflictSet, Relationship, SemanticIndex


def detect_affected_communities(
    base_index: SemanticIndex,
    id_map: Dict[str, str],
    merged_relationships: Dict[str, Relationship],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
) -> Set[str]:
    """Return the ids of communities affected by the merge.

    ``base_index`` supplies the community structure to diff against;
    ``changed_entity_ids`` and the reconciled edges/conflicts drive the
    detection. Must be complete (no false negatives).
    """
    raise NotImplementedError(
        "TODO(codex task 1): implement complete affected-community detection"
    )
