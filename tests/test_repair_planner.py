"""Unit tests for the local repair planner."""

from semantic_merge.repair_planner import compute_drift, plan_community_repair
from semantic_merge.schema import (
    Community,
    Entity,
    MergeConfig,
    RepairAction,
    Relationship,
    SemanticIndex,
    Summary,
)


def _base(n_members: int, coverage: float) -> SemanticIndex:
    idx = SemanticIndex()
    members = [f"m{i}" for i in range(n_members)]
    for m in members:
        idx.add_entity(Entity(id=m, name=m.upper()))
    idx.communities["c0"] = Community(id="c0", entity_ids=members)
    idx.summaries["s0"] = Summary(id="s0", community_id="c0", text="summary", coverage=coverage)
    return idx


def _plan(base, changed, rels=None, conflicts=None, config=None):
    config = config or MergeConfig()
    id_map = {e: e for e in base.entities}
    return plan_community_repair(
        "c0", base, id_map, rels or {}, conflicts or [], set(changed), config
    )


def test_unchanged_community_is_noop():
    base = _base(4, 1.0)
    assert compute_drift("c0", base, {}, {}, [], set(), MergeConfig()) == 0.0
    assert _plan(base, changed=[]).action is RepairAction.NOOP


def test_small_change_patches_summary():
    # one member changed, summary slightly under full coverage -> patch suffices.
    base = _base(5, 0.85)
    assert _plan(base, changed=["m0"]).action is RepairAction.PATCH_SUMMARY


def test_large_change_escalates():
    base = _base(4, 1.0)
    rels = {
        "e1": Relationship(id="e1", source="m0", target="m1", attributes={"conflicting": True}),
        "e2": Relationship(id="e2", source="m0", target="new1"),  # new entity attaches
    }
    decision = _plan(base, changed=["m0", "m1", "m2", "m3"], rels=rels)
    assert decision.action in (RepairAction.LOCAL_RECLUSTER, RepairAction.FULL_REGION_REBUILD)


def test_chooses_cheapest_under_threshold():
    # starting coverage 0.70 means PATCH (restores to 0.70) can't reach the 0.80
    # threshold, so the cheapest *feasible* action is REGENERATE_SUMMARY.
    base = _base(5, 0.70)
    assert _plan(base, changed=["m0"]).action is RepairAction.REGENERATE_SUMMARY
