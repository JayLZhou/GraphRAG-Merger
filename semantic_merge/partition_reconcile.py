"""Community-partition reconciliation (Stage 8).

Merging two indexes means merging two *independently computed* community
partitions of overlapping entity sets. A full re-clustering of the merged graph
would discard both indexes' partitioning (and summaries) and is exactly the cost
we want to avoid. Instead we reconcile:

  * **anchor** on the larger index's (hierarchical) partition — it carries the
    most structure and the most materialized summaries;
  * **remap** its members to canonical ids;
  * **attach** entities that are new (introduced by the smaller index) to the
    community of an already-placed neighbor, so the disturbance stays local;
  * **recompute** each community's internal relationship set against the
    reconciled edges.

The level / parent / children links are preserved, so the result is a
hierarchical partition the tree-DP repair planner can run over. (A symmetric,
modularity-optimizing reconciliation of *both* partitions is future work; this
anchor-and-attach scheme is the tractable default.)
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import Dict, List

from .schema import Community, Entity, Relationship, SemanticIndex


def reconcile_partitions(
    small: SemanticIndex,
    large: SemanticIndex,
    id_map: Dict[str, str],
    merged_entities: Dict[str, Entity],
    merged_relationships: Dict[str, Relationship],
) -> Dict[str, Community]:
    """Return the merged (hierarchical) community partition keyed by community id."""
    neighbors: Dict[str, List[str]] = defaultdict(list)
    member_edges: Dict[str, List[str]] = defaultdict(list)
    for rid, rel in merged_relationships.items():
        neighbors[rel.source].append(rel.target)
        neighbors[rel.target].append(rel.source)
        member_edges[rel.source].append(rid)
        member_edges[rel.target].append(rid)

    # 1. carry the larger index's hierarchy, remapping members to canonical ids.
    communities: Dict[str, Community] = {}
    ent2comm: Dict[str, str] = {}
    for cid, comm in large.communities.items():
        members = [id_map.get(e, e) for e in comm.entity_ids]
        members = [e for e in members if e in merged_entities]
        communities[cid] = dataclasses.replace(comm, entity_ids=members, relationship_ids=[])
        # only leaf-level assignment drives attachment (avoid double-placing in parents)
        if not comm.children_ids:
            for e in members:
                ent2comm[e] = cid

    # 2. attach new (small-only) entities to a placed neighbor's community.
    placed = set(ent2comm)
    for e in merged_entities:
        if e in placed:
            continue
        for nb in neighbors.get(e, []):
            if nb in ent2comm:
                cid = ent2comm[nb]
                communities[cid].entity_ids.append(e)
                ent2comm[e] = cid
                break
        # entities with no placed neighbor stay unassigned (a singleton region)

    # 3. recompute each community's internal relationship set.
    for cid, comm in communities.items():
        member_set = set(comm.entity_ids)
        rel_ids = sorted({
            rid
            for m in comm.entity_ids
            for rid in member_edges.get(m, [])
            if merged_relationships[rid].source in member_set
            and merged_relationships[rid].target in member_set
        })
        communities[cid] = dataclasses.replace(comm, relationship_ids=rel_ids)

    return communities
