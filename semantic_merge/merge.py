"""Binary merge orchestration.

``merge_two_indexes`` wires the pipeline together. The data flow below is the
contract between modules; the leaf steps are implemented in their own files
(see ``docs/codex_tasks.md``). The function is written out in full so the
intended composition is explicit even before every leaf is implemented.

Pipeline::

    pick smaller index  ->  discover bridges  ->  robust prune
        ->  lazy reverse consolidation  ->  merge entities  ->  reconcile edges
        ->  detect affected communities  ->  plan local repairs  ->  assemble
"""

from __future__ import annotations

from typing import Tuple

from . import affected_region, bridge, edge_reconcile, entity_merge, prune, repair_planner
from .schema import MergeConfig, SemanticIndex


def _orient(index_a: SemanticIndex, index_b: SemanticIndex) -> Tuple[SemanticIndex, SemanticIndex]:
    """Return ``(small, large)`` so bridge search runs forward from the smaller side.

    Forward search from the smaller index is what gives the
    ``O(N_small * log N_large)`` cost bound (see ``docs/theory.md``).
    """
    if index_a.n_entities <= index_b.n_entities:
        return index_a, index_b
    return index_b, index_a


def merge_two_indexes(
    index_a: SemanticIndex,
    index_b: SemanticIndex,
    config: MergeConfig,
) -> SemanticIndex:
    """Merge two semantic indexes into one consistent index.

    Steps (each delegated to its module):
      1. orient: choose the smaller index for forward bridge search;
      2. :func:`bridge.discover_entity_bridges`;
      3. :func:`prune.robust_semantic_prune`;
      4. lazy reverse consolidation — preserve reverse-direction candidates
         without paying for a second full search (deferred-resolution);
      5. :func:`entity_merge.merge_entities`;
      6. :func:`edge_reconcile.reconcile_edges`;
      7. :func:`affected_region.detect_affected_communities`;
      8. :func:`repair_planner.plan_local_repairs`;
      9. assemble the merged :class:`SemanticIndex` and apply the repair plan.
    """
    small, large = _orient(index_a, index_b)

    bridges = bridge.discover_entity_bridges(small, large, config)
    pruned = prune.robust_semantic_prune(bridges, small, large, config)

    # 4. lazy reverse consolidation: large-index entities with no forward match
    #    are carried over verbatim; their reverse candidacy is recorded for
    #    on-demand resolution rather than eagerly searched.
    # TODO(codex task 1): record lazy reverse candidates on the merged index.

    merged_entities, id_map, entity_conflicts = entity_merge.merge_entities(
        small, large, pruned, config
    )
    merged_relationships, edge_conflicts = edge_reconcile.reconcile_edges(
        small, large, id_map, config
    )

    changed_entity_ids = {
        old for old, new in id_map.items() if old != new
    }
    conflicts = list(entity_conflicts) + list(edge_conflicts)

    affected = affected_region.detect_affected_communities(
        large, id_map, merged_relationships, conflicts, changed_entity_ids
    )
    plan = repair_planner.plan_local_repairs(
        large, affected, id_map, conflicts, changed_entity_ids, config
    )

    # 9. assemble: start from the larger index's community/summary structure,
    #    swap in merged entities/edges, then apply ``plan`` to repair summaries.
    # TODO(codex task 1): build the merged SemanticIndex and apply ``plan``.
    raise NotImplementedError(
        "TODO(codex task 1): assemble merged index and apply repair plan; "
        f"pipeline reached planning with {len(affected)} affected communities"
    )
