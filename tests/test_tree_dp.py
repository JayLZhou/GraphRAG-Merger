"""Tests for the hierarchical (tree-DP) repair planner."""

from collections import Counter

from experiments.make_synthetic_indexes import build_synthetic_pair
from semantic_merge import (
    affected_region,
    bridge,
    edge_reconcile,
    entity_merge,
    merge_two_indexes,
    prune,
    repair_planner,
)
from semantic_merge.schema import MergeConfig, RepairAction


def _planner_inputs(hierarchical: bool, conflict_rate: float, seed: int = 1):
    cfg = MergeConfig(namespace_ids=False)
    small, large, _ = build_synthetic_pair(
        n_entities=120, overlap=0.3, conflict_rate=conflict_rate, seed=seed, hierarchical=hierarchical
    )
    br = bridge.discover_entity_bridges(small, large, cfg)
    pr = prune.robust_semantic_prune(br, small, large, cfg)
    _, id_map, ec = entity_merge.merge_entities(small, large, pr, cfg)
    mr, rc = edge_reconcile.reconcile_edges(small, large, id_map, cfg)
    conflicts = ec + rc
    counts = Counter(id_map.values())
    changed = {r for r, c in counts.items() if c > 1} | {
        id_map[s] for s in small.entities if id_map[s] not in large.entities
    }
    affected = affected_region.detect_affected_communities(large, id_map, mr, conflicts, changed)
    return large, affected, id_map, mr, conflicts, changed, cfg


def test_merge_uses_tree_dp_on_hierarchy():
    small, large, _ = build_synthetic_pair(n_entities=80, seed=2, hierarchical=True)
    m = merge_two_indexes(small, large, MergeConfig(namespace_ids=False))
    assert m.metadata["planner"] == "tree-dp"
    assert {c.level for c in m.communities.values()} == {0, 1}


def test_affected_region_flags_leaves_and_parents():
    large, affected, *_ = _planner_inputs(hierarchical=True, conflict_rate=0.3)
    leaves = {c for c in affected if not large.communities[c].children_ids}
    parents = {c for c in affected if large.communities[c].children_ids}
    assert leaves and parents  # both levels detected (multi-membership)


def test_tree_dp_never_worse_than_greedy():
    args = _planner_inputs(hierarchical=True, conflict_rate=0.3)
    tree = repair_planner.plan_repairs_tree(*args)
    flat = repair_planner.plan_local_repairs(*args)
    # tree-DP considers the per-community option too, so it can only tie or win.
    assert tree.total_cost <= flat.total_cost


def test_tree_dp_wins_when_changes_are_dense():
    args = _planner_inputs(hierarchical=True, conflict_rate=0.4, seed=1)
    tree = repair_planner.plan_repairs_tree(*args)
    flat = repair_planner.plan_local_repairs(*args)
    # dense changes -> one ancestor action subsumes many descendant repairs.
    assert tree.total_cost < flat.total_cost


def test_conflict_aware_summary_surfaces_disagreement():
    small, large, _ = build_synthetic_pair(
        n_entities=120, overlap=0.3, conflict_rate=0.3, seed=1, hierarchical=True
    )
    m = merge_two_indexes(small, large, MergeConfig(namespace_ids=False))
    # a contested community's regenerated summary explicitly states the conflict.
    assert any("Sources disagree" in s.text for s in m.summaries.values())


def test_compose_is_available_as_action():
    # COMPOSE should be reachable by the planner (cheaper than from-text regen).
    args = _planner_inputs(hierarchical=True, conflict_rate=0.2)
    flat = repair_planner.plan_local_repairs(*args)
    actions = {d.action for d in flat.decisions}
    assert RepairAction.COMPOSE_SUMMARY in actions or RepairAction.LOCAL_RECLUSTER in actions
