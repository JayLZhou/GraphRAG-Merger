"""Local repair planning.

For each affected community, choose the cheapest repair action that restores an
acceptable index. This is the cost-control core of the system: most merges
should resolve to NOOP / PATCH_SUMMARY, escalating to expensive actions
(recluster, rebuild) only where drift truly demands it.

Drift score for a community::

    drift = alpha * entity_change_ratio
          + beta  * edge_change_ratio
          + gamma * boundary_change
          + delta * conflict_density
          + epsilon * summary_coverage_drop

Action ladder (cheapest -> most expensive)::

    NOOP < PATCH_SUMMARY < REGENERATE_SUMMARY < LOCAL_RECLUSTER < FULL_REGION_REBUILD

Policy: pick the cheapest action whose post-repair state satisfies
``drift <= config.drift_threshold`` *and* ``coverage >= config.coverage_threshold``.
For independent communities this greedy per-community choice is optimal; for
hierarchical communities the optimal plan is a tree-DP over the community tree
(see ``docs/theory.md``). The MVP implements the independent-community case.
"""

from __future__ import annotations

from typing import Dict, List, Set

from .schema import (
    ConflictSet,
    MergeConfig,
    RepairPlan,
    SemanticIndex,
)


def compute_drift(
    community_id: str,
    base_index: SemanticIndex,
    id_map: Dict[str, str],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
    config: MergeConfig,
) -> float:
    """Compute the weighted drift score for a single community."""
    raise NotImplementedError("TODO(codex task 1): implement drift score")


def plan_local_repairs(
    base_index: SemanticIndex,
    affected_communities: Set[str],
    id_map: Dict[str, str],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
    config: MergeConfig,
) -> RepairPlan:
    """Produce a :class:`~semantic_merge.schema.RepairPlan` for the affected region.

    For each affected community compute drift and select the cheapest action
    satisfying the drift/coverage thresholds. Unaffected communities implicitly
    receive NOOP and need not appear in the plan.
    """
    raise NotImplementedError(
        "TODO(codex task 1): implement cheapest-action-under-threshold planner"
    )
