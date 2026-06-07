"""Affected-region detection.

The *affected region* is the set of communities whose membership, internal
edges, or boundary changed as a result of the merge. Repair should touch only
this region — that locality is what makes incremental merging cheaper than a
full rebuild.

A base community is affected if any of:
  * one of its (canonical) entities was fused / changed;
  * a new entity attaches to one of its members via a reconciled edge;
  * a conflicting edge is incident to its members;
  * an entity-level conflict (ambiguity / same-name) references its members.

Detection over-approximates on purpose: reporting an unchanged community is
merely wasteful, while *missing* a changed one is a correctness bug
(completeness, see ``docs/theory.md`` §6).
"""

from __future__ import annotations

from typing import Dict, List, Set

from .schema import ConflictKind, ConflictSet, Relationship, SemanticIndex

_ENTITY_CONFLICT_KINDS = {
    ConflictKind.AMBIGUOUS_BRIDGE,
    ConflictKind.SAME_NAME_DIFFERENT_ENTITY,
    ConflictKind.TEMPORAL_CONFLICT,
    ConflictKind.INCOMPATIBLE_TYPE,
}


def detect_affected_communities(
    base_index: SemanticIndex,
    id_map: Dict[str, str],
    merged_relationships: Dict[str, Relationship],
    conflicts: List[ConflictSet],
    changed_entity_ids: Set[str],
) -> Set[str]:
    """Return the ids of communities affected by the merge (complete superset)."""
    # An entity belongs to its leaf community AND every ancestor in the
    # hierarchy, so map each entity to ALL communities containing it (a plain
    # dict would collapse multi-level membership and miss leaves or parents).
    ent2comms: Dict[str, List[str]] = {}
    for comm in base_index.communities.values():
        for ent_id in comm.entity_ids:
            ent2comms.setdefault(ent_id, []).append(comm.id)
    base_entity_ids = set(base_index.entities)

    affected: Set[str] = set()

    def flag(ent_id: str) -> None:
        affected.update(ent2comms.get(ent_id, ()))

    # 1. fused / changed canonical entities.
    for cid in changed_entity_ids:
        flag(cid)

    # 2-3. edge-driven: new attachments and conflicting edges.
    for rel in merged_relationships.values():
        endpoints = (rel.source, rel.target)
        if rel.attributes.get("conflicting"):
            for ep in endpoints:
                flag(ep)
        new_eps = [ep for ep in endpoints if ep not in base_entity_ids]
        if len(new_eps) == 1:  # exactly one new endpoint attaching to the base
            for ep in endpoints:
                flag(ep)

    # 4. entity-level conflicts referencing community members.
    for cs in conflicts:
        if cs.kind not in _ENTITY_CONFLICT_KINDS:
            continue
        for member in cs.member_ids:
            flag(id_map.get(member, member))

    return affected
