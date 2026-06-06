"""Conflict-aware entity fusion.

Given pruned bridges, decide which entities actually fuse and build the merged
entity set plus a mapping from old entity ids to canonical ids (consumed by
``edge_reconcile``).

Decision policy:
  * **high-confidence** (retained) bridges fuse the two entities;
  * **low-confidence** pairs stay separate (they never reach ``retained``);
  * **ambiguous** pairs are *not* fused but recorded as conflict sets;
  * **same-name / incompatible-type or time** pairs become conflict sets too.

Fusion is loss-less on evidence: aliases, ``text_unit_ids``, and provenance are
unioned; the widest consistent validity interval is kept; descriptions are
preserved (longest as primary, all retained in ``attributes``). Canonical ids
anchor on the larger index so its community structure stays aligned.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Tuple

from . import util
from .schema import (
    ConflictKind,
    ConflictSet,
    Entity,
    MergeConfig,
    PruneResult,
    SemanticIndex,
)


class _UnionFind:
    """Union-find that prefers ``preferred`` (large-side) ids as group roots."""

    def __init__(self, ids: List[str], preferred: Set[str]):
        self.parent: Dict[str, str] = {i: i for i in ids}
        self.preferred = preferred

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # Prefer a large-side root; otherwise pick deterministically.
        a_pref, b_pref = ra in self.preferred, rb in self.preferred
        if a_pref and not b_pref:
            root, other = ra, rb
        elif b_pref and not a_pref:
            root, other = rb, ra
        else:
            root, other = (ra, rb) if ra < rb else (rb, ra)
        self.parent[other] = root


def _dedup_keep_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _fuse(group: List[Entity], canonical_id: str, large_ids: Set[str]) -> Entity:
    """Fuse a group of co-referent entities into one canonical entity."""
    primary = next((e for e in group if e.id == canonical_id), group[0])

    # name: keep the canonical/anchor name; collect every label as an alias.
    name = primary.name
    name_norm = util.normalize_name(name)
    alias_labels: List[str] = []
    descriptions: List[str] = []
    text_units: List[str] = []
    provenance_sources: List[dict] = []
    attributes: Dict[str, object] = {}
    chosen_type = primary.type
    embedding = primary.embedding
    valids_from = [e.valid_from for e in group if e.valid_from]
    valids_to = [e.valid_to for e in group if e.valid_to]
    created = [e.created_at for e in group if e.created_at]
    updated = [e.updated_at for e in group if e.updated_at]

    for e in group:
        for label in [e.name, *e.aliases]:
            if util.normalize_name(label) != name_norm:
                alias_labels.append(label)
        if e.description:
            descriptions.append(e.description)
        text_units.extend(e.text_unit_ids)
        provenance_sources.append(
            {"id": e.id, "index": "large" if e.id in large_ids else "small"}
        )
        if chosen_type is None and e.type is not None:
            chosen_type = e.type
        if embedding is None and e.embedding is not None:
            embedding = e.embedding
        attributes.update(e.attributes)

    descriptions = _dedup_keep_order(descriptions)
    primary_desc = max(descriptions, key=len) if descriptions else None
    if len(descriptions) > 1:
        attributes["descriptions"] = descriptions
    if len(group) > 1:
        attributes["fused_from"] = [e.id for e in group]

    provenance: Dict[str, object] = dict(primary.provenance)
    provenance["sources"] = provenance_sources

    return Entity(
        id=canonical_id,
        name=name,
        type=chosen_type,
        description=primary_desc,
        aliases=_dedup_keep_order(alias_labels),
        text_unit_ids=_dedup_keep_order(text_units),
        embedding=embedding,
        valid_from=min(valids_from) if valids_from else None,
        valid_to=max(valids_to) if valids_to else None,
        created_at=min(created) if created else None,
        updated_at=max(updated) if updated else None,
        provenance=provenance,
        attributes=attributes,
    )


def merge_entities(
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    pruned: PruneResult,
    config: MergeConfig,
) -> Tuple[Dict[str, Entity], Dict[str, str], List[ConflictSet]]:
    """Fuse entities according to pruned bridges.

    Returns ``(merged_entities, id_map, conflicts)`` where ``id_map`` covers
    every entity id in both indexes (fused or not).
    """
    large_ids = set(index_large.entities)
    all_ids = list(index_small.entities) + list(index_large.entities)
    uf = _UnionFind(all_ids, preferred=large_ids)

    for bridge in pruned.retained:
        uf.union(bridge.source_id, bridge.target_id)

    # Group entities by canonical root.
    by_id: Dict[str, Entity] = {**index_large.entities, **index_small.entities}
    groups: Dict[str, List[Entity]] = defaultdict(list)
    id_map: Dict[str, str] = {}
    for ent_id in all_ids:
        root = uf.find(ent_id)
        id_map[ent_id] = root
        groups[root].append(by_id[ent_id])

    merged_entities = {root: _fuse(group, root, large_ids) for root, group in groups.items()}

    # Preserve ambiguity and conflict as ConflictSets (no silent drops).
    conflicts: List[ConflictSet] = []
    for amb in pruned.ambiguities:
        members = [amb.source_id] + [c.target_id for c in amb.candidates]
        conflicts.append(
            ConflictSet(
                id=f"ambig::{amb.source_id}",
                kind=ConflictKind.AMBIGUOUS_BRIDGE,
                member_ids=members,
                reason=f"{len(amb.candidates)} plausible matches; not auto-fused",
            )
        )
    for c in pruned.conflicts:
        temporal = c.features.get("temporal", 1.0) == 0.0
        kind = ConflictKind.TEMPORAL_CONFLICT if temporal else ConflictKind.SAME_NAME_DIFFERENT_ENTITY
        conflicts.append(
            ConflictSet(
                id=f"conflict::{c.source_id}::{c.target_id}",
                kind=kind,
                member_ids=[c.source_id, c.target_id],
                reason="same name, incompatible "
                + ("time" if temporal else "type")
                + "; kept separate",
            )
        )

    return merged_entities, id_map, conflicts
