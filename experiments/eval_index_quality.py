"""Index-quality metrics for a merged index, scored against ground truth.

Metrics:
  * **entity_duplicate_rate**            — fraction of true duplicate groups left
    un-fused (lower better; fusion *recall*).
  * **wrong_merge_rate**                 — fraction of same-name-distinct pairs
    wrongly fused (lower better; fusion *precision*).
  * **edge_conflict_preservation_rate**  — fraction of planted conflicts kept as
    conflict sets (higher better).
  * **n_affected_communities**           — size of the disturbed region.
  * **n_repaired_summaries**             — non-NOOP repair actions taken.

The headline: the semantic merge gets a low duplicate rate AND a low wrong-merge
rate AND high conflict preservation simultaneously — the Pareto point the naive
and name-only baselines cannot reach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from experiments.make_synthetic_indexes import GroundTruth
from semantic_merge.schema import ConflictKind, SemanticIndex


@dataclass
class QualityReport:
    entity_duplicate_rate: float
    wrong_merge_rate: float
    edge_conflict_preservation_rate: float
    n_affected_communities: int
    n_repaired_summaries: int


def evaluate_quality(merged: SemanticIndex, truth: GroundTruth) -> QualityReport:
    """Score ``merged`` against planted ``truth`` (assumes ids un-namespaced)."""
    id_map: Dict[str, str] = merged.metadata.get("id_map", {})

    def canon(x: str) -> str:
        return id_map.get(x, x)

    # fusion recall: a group is correctly fused iff all members share a canon id.
    missed = sum(1 for ids in truth.duplicate_groups.values()
                 if len({canon(i) for i in ids}) > 1)
    n_groups = len(truth.duplicate_groups)
    entity_duplicate_rate = missed / n_groups if n_groups else 0.0

    # fusion precision: same-name-distinct pairs must NOT share a canon id.
    wrong = sum(1 for a, b in truth.same_name_distinct if canon(a) == canon(b))
    n_distinct = len(truth.same_name_distinct)
    wrong_merge_rate = wrong / n_distinct if n_distinct else 0.0

    # conflict preservation: planted (large_rel, small_rel) both in a conflict set.
    conflict_sets: List[Set[str]] = [
        set(c.member_ids) for c in merged.metadata.get("conflicts", [])
        if c.kind == ConflictKind.CONTRADICTORY_RELATIONSHIP
    ]
    preserved = sum(1 for lr, sr in truth.relationship_conflicts
                    if any({lr, sr} <= ms for ms in conflict_sets))
    n_conf = len(truth.relationship_conflicts)
    edge_conflict_preservation_rate = preserved / n_conf if n_conf else 1.0

    plan = merged.metadata.get("repair_plan")
    n_repaired = len(plan.decisions) if plan is not None else 0

    return QualityReport(
        entity_duplicate_rate=entity_duplicate_rate,
        wrong_merge_rate=wrong_merge_rate,
        edge_conflict_preservation_rate=edge_conflict_preservation_rate,
        n_affected_communities=len(merged.metadata.get("affected_communities", [])),
        n_repaired_summaries=n_repaired,
    )
