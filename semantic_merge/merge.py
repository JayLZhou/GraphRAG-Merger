"""Binary merge orchestration.

``merge_two_indexes`` wires the pipeline together::

    pick smaller index  ->  discover bridges  ->  robust prune
        ->  lazy reverse consolidation  ->  merge entities  ->  reconcile edges
        ->  detect affected communities  ->  plan local repairs  ->  assemble

The result's ``metadata`` carries the merge audit trail: the ``id_map``, the
preserved ``conflicts``, the ``repair_plan``, the affected communities, and
bridge-comparison counts — consumed by the evaluation scripts.
"""

from __future__ import annotations

import dataclasses
import math
import random
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from . import affected_region, bridge, edge_reconcile, entity_merge, prune, repair_planner, util
from .schema import (
    Community,
    MergeConfig,
    RepairAction,
    RepairPlan,
    SemanticIndex,
    Summary,
)


def _orient(a: SemanticIndex, b: SemanticIndex) -> Tuple[SemanticIndex, SemanticIndex]:
    """Return ``(small, large)`` so bridge search runs forward from the smaller side."""
    return (a, b) if a.n_entities <= b.n_entities else (b, a)


def _namespace(index: SemanticIndex, tag: str) -> SemanticIndex:
    """Return a copy of ``index`` with every id prefixed ``tag:`` (collision-free)."""
    p = f"{tag}:"

    def pid(x):
        return f"{p}{x}" if x is not None else None

    return SemanticIndex(
        name=index.name,
        embedding_dim=index.embedding_dim,
        metadata=dict(index.metadata),
        text_units={pid(t.id): dataclasses.replace(t, id=pid(t.id)) for t in index.text_units.values()},
        entities={
            pid(e.id): dataclasses.replace(e, id=pid(e.id), text_unit_ids=[pid(x) for x in e.text_unit_ids])
            for e in index.entities.values()
        },
        relationships={
            pid(r.id): dataclasses.replace(
                r,
                id=pid(r.id),
                source=pid(r.source),
                target=pid(r.target),
                text_unit_ids=[pid(x) for x in r.text_unit_ids],
            )
            for r in index.relationships.values()
        },
        communities={
            pid(c.id): dataclasses.replace(
                c,
                id=pid(c.id),
                entity_ids=[pid(x) for x in c.entity_ids],
                relationship_ids=[pid(x) for x in c.relationship_ids],
                parent_id=pid(c.parent_id),
                children_ids=[pid(x) for x in c.children_ids],
            )
            for c in index.communities.values()
        },
        summaries={
            pid(s.id): dataclasses.replace(s, id=pid(s.id), community_id=pid(s.community_id))
            for s in index.summaries.values()
        },
    )


def _regenerate_summary_text(community: Community, merged: SemanticIndex, action: RepairAction) -> str:
    names = [merged.entities[e].name for e in community.entity_ids if e in merged.entities]
    head = ", ".join(sorted(names)[:8])
    return f"[{action.value}] {community.title or community.id}: {head}".strip()


def merge_two_indexes(
    index_a: SemanticIndex,
    index_b: SemanticIndex,
    config: MergeConfig,
) -> SemanticIndex:
    """Merge two semantic indexes into one consistent index (see module docstring)."""
    small, large = _orient(index_a, index_b)
    if config.namespace_ids:
        small, large = _namespace(small, "S"), _namespace(large, "L")

    # 2-3. discover + prune bridges (forward, smaller -> larger).
    bridges = bridge.discover_entity_bridges(small, large, config)
    pruned = prune.robust_semantic_prune(bridges, small, large, config)

    # 5-6. conflict-aware entity fusion (step 4 lazy reverse is implicit: any
    #      large entity with no forward match keeps its own canonical id, and we
    #      record that reverse search was deferred rather than run eagerly).
    merged_entities, id_map, entity_conflicts = entity_merge.merge_entities(small, large, pruned, config)
    merged_relationships, edge_conflicts = edge_reconcile.reconcile_edges(small, large, id_map, config)
    conflicts = entity_conflicts + edge_conflicts

    # Canonical ids that changed: fusion roots (absorbed >1 original) + new
    # entities introduced by the smaller index.
    counts = Counter(id_map.values())
    fused_roots = {root for root, c in counts.items() if c > 1}
    new_from_small = {id_map[s] for s in small.entities if id_map[s] not in large.entities}
    changed_entity_ids: Set[str] = fused_roots | new_from_small

    # 7-8. localize the disturbance and plan the cheapest repairs.
    affected = affected_region.detect_affected_communities(
        large, id_map, merged_relationships, conflicts, changed_entity_ids
    )
    plan = repair_planner.plan_local_repairs(
        large, affected, id_map, merged_relationships, conflicts, changed_entity_ids, config
    )

    # 9. assemble: anchor on the larger index's community structure.
    merged = SemanticIndex(name=f"merged({index_a.name},{index_b.name})")
    merged.embedding_dim = large.embedding_dim or small.embedding_dim
    merged.text_units = {**large.text_units, **small.text_units}
    merged.entities = merged_entities
    merged.relationships = merged_relationships

    # Communities carried from base, with relationship_ids recomputed against the
    # reconciled edges so they stay consistent.
    members_to_edges: Dict[str, List[str]] = {}
    for rid, rel in merged_relationships.items():
        members_to_edges.setdefault(rel.source, []).append(rid)
        members_to_edges.setdefault(rel.target, []).append(rid)
    for cid, comm in large.communities.items():
        member_set = set(comm.entity_ids)
        rel_ids = sorted(
            {rid for m in comm.entity_ids for rid in members_to_edges.get(m, [])
             if merged_relationships[rid].source in member_set
             and merged_relationships[rid].target in member_set}
        )
        merged.communities[cid] = dataclasses.replace(comm, relationship_ids=rel_ids)

    # Summaries carried from base, with the repair plan applied.
    decisions = {d.community_id: d for d in plan.decisions}
    for sid, summ in large.summaries.items():
        decision = decisions.get(summ.community_id)
        new_summ = dataclasses.replace(summ, attributes=dict(summ.attributes))
        if decision is None or decision.action is RepairAction.NOOP:
            pass  # unchanged
        elif decision.action is RepairAction.PATCH_SUMMARY:
            new_summ.stale = False
            new_summ.attributes["repair"] = decision.action.value
        else:  # REGENERATE_SUMMARY / LOCAL_RECLUSTER / FULL_REGION_REBUILD
            comm = merged.communities.get(summ.community_id)
            if comm is not None:
                new_summ.text = _regenerate_summary_text(comm, merged, decision.action)
            new_summ.coverage = 1.0
            new_summ.stale = False
            new_summ.attributes["repair"] = decision.action.value
        merged.summaries[sid] = new_summ

    merged.metadata = {
        "id_map": id_map,
        "conflicts": conflicts,
        "repair_plan": plan,
        "affected_communities": sorted(affected),
        "bridge_comparisons": bridges.comparisons,
        "n_entities_in": small.n_entities + large.n_entities,
        "n_entities_out": len(merged_entities),
        "n_fused": len(fused_roots),
        "lazy_reverse_deferred": True,
    }
    return merged


# ---------------------------------------------------------------------------
# Multi-index merge planning (docs/theory.md §9)
# ---------------------------------------------------------------------------

_STRATEGIES = ("random", "small_first", "large_first", "semantic_aware")


def _norm_names(index: SemanticIndex) -> Set[str]:
    return {util.normalize_name(e.name) for e in index.entities.values()}


def _name_tokens(index: SemanticIndex) -> Set[str]:
    toks: Set[str] = set()
    for e in index.entities.values():
        toks.update(util.alias_token_set(e))
    return toks


def estimate_merge_cost(a: SemanticIndex, b: SemanticIndex, config: MergeConfig) -> float:
    """Estimated cost-per-benefit ``C_hat / (1 + benefit)`` of merging ``a`` and ``b``.

    Cheap, structural proxies (no actual merge): name overlap stands in for
    candidate pairs and duplicate-reduction benefit; type-mismatched shared
    names stand in for conflict risk; communities touched by shared names stand
    in for the affected region and its summary-repair cost. Lower is better.
    """
    na, nb = a.n_entities, b.n_entities
    if na == 0 or nb == 0:
        return float("inf")
    n_small, n_large = min(na, nb), max(na, nb)
    large = a if na >= nb else b

    names_a, names_b = _norm_names(a), _norm_names(b)
    shared = names_a & names_b
    overlap = len(shared)
    tok_overlap = len(_name_tokens(a) & _name_tokens(b))
    candidate_pairs = overlap + 0.1 * tok_overlap

    types_a = {util.normalize_name(e.name): e.type for e in a.entities.values()}
    types_b = {util.normalize_name(e.name): e.type for e in b.entities.values()}
    conflict_risk = sum(1 for nm in shared if types_a.get(nm) != types_b.get(nm))

    affected = 0
    for comm in large.communities.values():
        if any(util.normalize_name(large.entities[e].name) in shared
               for e in comm.entity_ids if e in large.entities):
            affected += 1
    avg_comm = n_large / max(len(large.communities), 1)
    summary_repair = affected * avg_comm

    cost = (
        config.c_alpha * n_small * math.log(n_large + 1)
        + config.c_beta * candidate_pairs
        + config.c_gamma * conflict_risk
        + config.c_delta * affected
        + config.c_epsilon * summary_repair
    )
    benefit = float(overlap)  # overlap + duplicate_reduction
    return cost / (1.0 + benefit)


def _select_pair(
    work: List[SemanticIndex], strategy: str, config: MergeConfig, rng: random.Random
) -> Tuple[int, int]:
    n = len(work)
    if strategy == "random":
        i, j = rng.sample(range(n), 2)
        return (i, j) if i < j else (j, i)
    if strategy in ("small_first", "large_first"):
        order = sorted(range(n), key=lambda k: work[k].n_entities, reverse=(strategy == "large_first"))
        i, j = order[0], order[1]
        return (i, j) if i < j else (j, i)
    if strategy == "semantic_aware":
        best, best_score = (0, 1), float("inf")
        for i in range(n):
            for j in range(i + 1, n):
                score = estimate_merge_cost(work[i], work[j], config)
                if score < best_score:
                    best, best_score = (i, j), score
        return best
    raise ValueError(f"unknown strategy {strategy!r}; choose from {_STRATEGIES}")


def merge_k_indexes(
    indexes: List[SemanticIndex],
    config: MergeConfig,
    strategy: str = "semantic_aware",
    seed: int = 0,
) -> SemanticIndex:
    """Merge ``k`` indexes into one by repeated binary merge, ordered by ``strategy``.

    Strategies: ``random``, ``small_first``, ``large_first``, ``semantic_aware``
    (greedily merge the pair minimizing :func:`estimate_merge_cost`). The final
    index's metadata records ``total_bridge_comparisons`` and the ``merge_order``.
    """
    if not indexes:
        raise ValueError("merge_k_indexes requires at least one index")
    work = list(indexes)
    rng = random.Random(seed)
    total_comparisons = 0
    order: List[Tuple[Optional[str], Optional[str]]] = []

    while len(work) > 1:
        i, j = _select_pair(work, strategy, config, rng)
        a, b = work[i], work[j]
        merged = merge_two_indexes(a, b, config)
        total_comparisons += int(merged.metadata.get("bridge_comparisons", 0))
        order.append((a.name, b.name))
        work = [w for k, w in enumerate(work) if k not in (i, j)]
        work.append(merged)

    final = work[0]
    final.metadata["total_bridge_comparisons"] = total_comparisons
    final.metadata["merge_order"] = order
    final.metadata["strategy"] = strategy
    return final
