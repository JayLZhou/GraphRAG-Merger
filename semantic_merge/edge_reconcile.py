"""Relationship (edge) reconciliation.

After entities are fused, edges are re-pointed at canonical endpoints and
de-duplicated, while *preserving contradictions* as conflict sets rather than
overwriting them.

Steps:
  1. **remap endpoints** through the entity ``id_map`` to canonical ids;
  2. **group** by ``(source, target, relation_type)``;
  3. detect **contradiction**: two edges in a group asserting different
     ``attributes["claim"]`` values are kept as separate edges and recorded in a
     :class:`ConflictSet` (kind ``CONTRADICTORY_RELATIONSHIP``);
  4. **version temporal updates**: within a compatible (same-claim) group, edges
     with distinct timestamps become an ordered version chain (latest marked
     current, earlier ``superseded_by`` the next) — the older fact is not lost;
  5. **merge** the remaining compatible duplicates into one edge, unioning
     evidence (``text_unit_ids``, provenance) and taking the max weight.

Invariant: evidence is never silently overwritten.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .schema import (
    ConflictKind,
    ConflictSet,
    MergeConfig,
    Relationship,
    SemanticIndex,
)


def _time_key(rel: Relationship) -> Optional[str]:
    return rel.valid_from or rel.timestamp


def _merge_edges(
    edges: List[Relationship],
    source: str,
    target: str,
    rel_id: str,
    small_rel_ids: Set[str],
) -> Relationship:
    """Merge compatible edges into one, unioning evidence (loss-less)."""
    text_units: List[str] = []
    sources: List[dict] = []
    descriptions: List[str] = []
    froms = [e.valid_from for e in edges if e.valid_from]
    tos = [e.valid_to for e in edges if e.valid_to]
    times = [t for t in (_time_key(e) for e in edges) if t]
    attributes: Dict[str, object] = {}
    seen_tu: Set[str] = set()

    for e in edges:
        for tu in e.text_unit_ids:
            if tu not in seen_tu:
                seen_tu.add(tu)
                text_units.append(tu)
        if e.description:
            descriptions.append(e.description)
        sources.append({"id": e.id, "index": "small" if e.id in small_rel_ids else "large"})
        attributes.update(e.attributes)

    primary = edges[0]
    return Relationship(
        id=rel_id,
        source=source,
        target=target,
        relation_type=primary.relation_type,
        description=max(descriptions, key=len) if descriptions else None,
        weight=max((e.weight for e in edges), default=1.0),
        text_unit_ids=text_units,
        valid_from=min(froms) if froms else None,
        valid_to=max(tos) if tos else None,
        timestamp=max(times) if times else None,
        provenance={"sources": sources},
        attributes=attributes,
    )


def reconcile_edges(
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    id_map: Dict[str, str],
    config: MergeConfig,
) -> Tuple[Dict[str, Relationship], List[ConflictSet]]:
    """Remap, group, and reconcile relationships from both indexes."""
    small_rel_ids = set(index_small.relationships)

    # 1-2. remap endpoints and group by (source, target, relation_type).
    groups: Dict[Tuple[str, str, str], List[Relationship]] = defaultdict(list)
    for rel in list(index_large.relationships.values()) + list(index_small.relationships.values()):
        cs = id_map.get(rel.source, rel.source)
        ct = id_map.get(rel.target, rel.target)
        rtype = (rel.relation_type or "").strip().lower()
        groups[(cs, ct, rtype)].append(rel)

    merged: Dict[str, Relationship] = {}
    conflicts: List[ConflictSet] = []

    for (cs, ct, rtype), edges in groups.items():
        base = f"{cs}|{ct}|{rtype}"

        # 3. partition by claim; >=2 distinct claims => contradiction.
        by_claim: Dict[Optional[str], List[Relationship]] = defaultdict(list)
        for e in edges:
            by_claim[e.attributes.get("claim")].append(e)
        distinct_claims = [c for c in by_claim if c is not None]

        if len(distinct_claims) >= 2:
            members: List[str] = []
            for claim, claim_edges in by_claim.items():
                suffix = f"|claim={claim}" if claim is not None else ""
                rid = f"{base}{suffix}"
                m = _merge_edges(claim_edges, cs, ct, rid, small_rel_ids)
                m.attributes["conflicting"] = True
                merged[rid] = m
                members.extend(e.id for e in claim_edges)
            conflicts.append(
                ConflictSet(
                    id=f"edge-conflict::{base}",
                    kind=ConflictKind.CONTRADICTORY_RELATIONSHIP,
                    member_ids=members,
                    reason=f"contradictory claims {sorted(distinct_claims)} kept separate",
                )
            )
            continue

        # 4-5. compatible group: version distinct timestamps, else merge.
        time_buckets: Dict[Optional[str], List[Relationship]] = defaultdict(list)
        for e in edges:
            time_buckets[_time_key(e)].append(e)
        distinct_times = [t for t in time_buckets if t is not None]

        if len(distinct_times) >= 2:
            ordered = sorted(distinct_times)
            versioned_ids: List[str] = []
            for i, t in enumerate(ordered):
                rid = f"{base}|t={t}"
                m = _merge_edges(time_buckets[t], cs, ct, rid, small_rel_ids)
                m.attributes["version"] = i
                versioned_ids.append(rid)
                merged[rid] = m
            # absorb any timeless edges into the earliest version's evidence
            for e in time_buckets.get(None, []):
                merged[versioned_ids[0]].text_unit_ids.extend(
                    tu for tu in e.text_unit_ids if tu not in merged[versioned_ids[0]].text_unit_ids
                )
            for i, rid in enumerate(versioned_ids):
                if i + 1 < len(versioned_ids):
                    merged[rid].attributes["superseded_by"] = versioned_ids[i + 1]
                else:
                    merged[rid].attributes["current"] = True
        else:
            merged[base] = _merge_edges(edges, cs, ct, base, small_rel_ids)

    return merged, conflicts
