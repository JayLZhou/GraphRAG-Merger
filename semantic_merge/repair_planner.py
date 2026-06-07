"""Local repair planning.

For each affected community, choose the cheapest repair action that restores an
acceptable index. This is the cost-control core of the system: most merges
resolve to NOOP / PATCH_SUMMARY, escalating to expensive actions only where
drift truly demands it.

Drift score for a community::

    drift = alpha * entity_change_ratio
          + beta  * edge_change_ratio
          + gamma * boundary_change
          + delta * conflict_density
          + epsilon * summary_coverage_drop

Each action repairs a subset of those components (and so removes their
contribution to the *residual* drift):

    NOOP                 repairs nothing
    PATCH_SUMMARY        summary coverage (epsilon)
    REGENERATE_SUMMARY   + conflicts now described (delta)
    LOCAL_RECLUSTER      + structure: edges, boundary (beta, gamma) -> residual = alpha*ecr
    FULL_REGION_REBUILD  everything -> residual 0

Policy: pick the cheapest action whose residual drift ``<= drift_threshold`` and
post-repair coverage ``>= coverage_threshold``. Costs are monotone along the
ladder, so scanning the ladder and returning the first feasible action yields
the cheapest feasible action — which for independent communities is the global
optimum (``docs/theory.md`` §7).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .schema import (
    ConflictKind,
    ConflictSet,
    MergeConfig,
    RepairAction,
    RepairDecision,
    RepairPlan,
    Relationship,
    SemanticIndex,
)


def _community_summary(base_index: SemanticIndex, community_id: str):
    for s in base_index.summaries.values():
        if s.community_id == community_id:
            return s
    return None


def _approx_tokens(text: Optional[str]) -> float:
    """Rough token count (~4 chars/token) for cost estimation."""
    return len(text) / 4.0 if text else 0.0


def _content_tokens(base_index: SemanticIndex, members: Set[str]) -> float:
    """Approximate source-text tokens behind a community (for cost estimation)."""
    total = 0.0
    for m in members:
        ent = base_index.entities.get(m)
        if ent is None:
            continue
        total += _approx_tokens(ent.description)
        for tu_id in ent.text_unit_ids:
            tu = base_index.text_units.get(tu_id)
            if tu is not None:
                total += float(tu.n_tokens) if tu.n_tokens else _approx_tokens(tu.text)
    return total


def _drift_components(
    community_id: str,
    base_index: SemanticIndex,
    id_map: Dict[str, str],
    merged_relationships: Dict[str, Relationship],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
    config: MergeConfig,
) -> Tuple[float, Dict[str, float]]:
    """Return ``(drift, info)`` where info carries components, coverage, size."""
    comm = base_index.communities[community_id]
    member_set = set(comm.entity_ids)
    n = max(len(member_set), 1)
    n_edges = max(len(comm.relationship_ids), 1)
    base_entity_ids = set(base_index.entities)

    entity_change_ratio = sum(1 for m in member_set if m in changed_entity_ids) / n

    edge_changes = 0
    boundary_new = 0
    conflict_count = 0
    for rel in merged_relationships.values():
        s_in, t_in = rel.source in member_set, rel.target in member_set
        if not (s_in or t_in):
            continue
        if rel.attributes.get("conflicting"):
            edge_changes += 1
            conflict_count += 1
        if "version" in rel.attributes:
            edge_changes += 1
        new_s, new_t = rel.source not in base_entity_ids, rel.target not in base_entity_ids
        if (s_in and new_t) or (t_in and new_s):
            boundary_new += 1

    for cs in conflicts:
        if cs.kind == ConflictKind.CONTRADICTORY_RELATIONSHIP:
            continue  # already counted via conflicting edges
        if any(id_map.get(m, m) in member_set for m in cs.member_ids):
            conflict_count += 1

    edge_change_ratio = min(1.0, edge_changes / n_edges)
    boundary_change = min(1.0, boundary_new / n)
    conflict_density = min(1.0, conflict_count / n)

    summary = _community_summary(base_index, community_id)
    has_summary = summary is not None
    old_coverage = summary.coverage if has_summary else 1.0
    cov_change = min(1.0, entity_change_ratio + boundary_change)
    summary_coverage_drop = old_coverage * cov_change if has_summary else 0.0

    drift = (
        config.alpha * entity_change_ratio
        + config.beta * edge_change_ratio
        + config.gamma * boundary_change
        + config.delta * conflict_density
        + config.epsilon * summary_coverage_drop
    )
    info = {
        "ecr": entity_change_ratio,
        "ech": edge_change_ratio,
        "bnd": boundary_change,
        "cd": conflict_density,
        "scd": summary_coverage_drop,
        "old_coverage": old_coverage,
        "cov_change": cov_change,
        "has_summary": 1.0 if has_summary else 0.0,
        "n": float(n),
        # cost-model inputs (token-grounded)
        "content_tokens": _content_tokens(base_index, member_set),
        "summary_tokens": _approx_tokens(summary.text) if has_summary else 0.0,
        "n_sub": float(len(comm.children_ids) or max(2, n // 8)),
    }
    return drift, info


def compute_drift(
    community_id: str,
    base_index: SemanticIndex,
    id_map: Dict[str, str],
    merged_relationships: Dict[str, Relationship],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
    config: MergeConfig,
) -> float:
    """Compute the weighted drift score for a single community."""
    drift, _ = _drift_components(
        community_id, base_index, id_map, merged_relationships, conflicts, changed_entity_ids, config
    )
    return drift


def _action_cost(action: RepairAction, info: Dict[str, float], config: MergeConfig) -> float:
    """Token-grounded cost of an action via the configured CostModel."""
    return config.cost_model.cost(
        action,
        content_tokens=info["content_tokens"],
        summary_tokens=info["summary_tokens"],
        n_sub=int(info["n_sub"]),
    )


def _residual_and_coverage(
    action: RepairAction, drift: float, info: Dict[str, float], config: MergeConfig
) -> Tuple[float, float]:
    old_cov, cov_change = info["old_coverage"], info["cov_change"]
    if action is RepairAction.NOOP:
        cov = 1.0 if not info["has_summary"] else old_cov * (1.0 - cov_change)
        return drift, cov
    if action is RepairAction.PATCH_SUMMARY:
        cov = 1.0 if not info["has_summary"] else old_cov
        return drift - config.epsilon * info["scd"], cov
    if action is RepairAction.REGENERATE_SUMMARY:
        return drift - config.epsilon * info["scd"] - config.delta * info["cd"], 1.0
    if action is RepairAction.LOCAL_RECLUSTER:
        return config.alpha * info["ecr"], 1.0
    return 0.0, 1.0  # FULL_REGION_REBUILD


# Cheapest-first ladder.
_LADDER = [
    RepairAction.NOOP,
    RepairAction.PATCH_SUMMARY,
    RepairAction.REGENERATE_SUMMARY,
    RepairAction.LOCAL_RECLUSTER,
    RepairAction.FULL_REGION_REBUILD,
]


def plan_community_repair(
    community_id: str,
    base_index: SemanticIndex,
    id_map: Dict[str, str],
    merged_relationships: Dict[str, Relationship],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
    config: MergeConfig,
) -> RepairDecision:
    """Pick the cheapest feasible action for a single community."""
    drift, info = _drift_components(
        community_id, base_index, id_map, merged_relationships, conflicts, changed_entity_ids, config
    )
    # Among all actions that satisfy the drift/coverage constraints, pick the
    # one with minimum token cost. The ladder is NOT cost-monotone under a real
    # cost model (e.g. LOCAL_RECLUSTER can exceed FULL_REGION_REBUILD for small
    # communities), so we minimize cost explicitly rather than take the first
    # feasible action. Ties break toward the earlier (simpler) ladder action.
    best: Optional[RepairDecision] = None
    for action in _LADDER:
        residual, coverage = _residual_and_coverage(action, drift, info, config)
        if residual <= config.drift_threshold and coverage >= config.coverage_threshold:
            cost = _action_cost(action, info, config)
            if best is None or cost < best.estimated_cost:
                best = RepairDecision(
                    community_id=community_id,
                    action=action,
                    drift=drift,
                    estimated_cost=cost,
                    coverage_after=coverage,
                    rationale=f"min-cost feasible: residual={residual:.3f}<=tau, "
                    f"coverage={coverage:.3f}>=kappa, cost={cost:.0f} tok",
                )
    # FULL_REGION_REBUILD always satisfies the constraints, so best is never None.
    assert best is not None, "no feasible repair action (should never happen)"
    return best


def plan_local_repairs(
    base_index: SemanticIndex,
    affected_communities: Set[str],
    id_map: Dict[str, str],
    merged_relationships: Dict[str, Relationship],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
    config: MergeConfig,
) -> RepairPlan:
    """Produce a repair plan for the affected region (NOOP communities omitted)."""
    decisions: List[RepairDecision] = []
    for cid in sorted(affected_communities):
        if cid not in base_index.communities:
            continue
        decision = plan_community_repair(
            cid, base_index, id_map, merged_relationships, conflicts, changed_entity_ids, config
        )
        if decision.action is not RepairAction.NOOP:
            decisions.append(decision)
    return RepairPlan(decisions=decisions)
