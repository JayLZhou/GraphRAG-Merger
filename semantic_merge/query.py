"""Certain / possible answering over a conflict-tolerant merged index (Stage IV).

The merge does **not** resolve contradictions; it keeps every source's claim with
provenance. A *repair* is one consistent way to resolve all conflicts (pick one
claim per conflict). Following consistent-query-answering semantics:

  * a **certain** answer holds in *every* repair;
  * a **possible** answer holds in *some* repair.

Because conflicts here are local and mutually independent (each contradiction
involves one ``(source, target, relation_type)`` group or one entity), we can
answer atomic queries directly from the relevant group — without enumerating the
exponentially many repairs. Atomic relationship/attribute/existence queries are
therefore PTIME.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import util
from .schema import SemanticIndex


def _canon(index: SemanticIndex, entity_id: str) -> str:
    return index.metadata.get("id_map", {}).get(entity_id, entity_id)


def query_relationship(
    index: SemanticIndex,
    source_id: str,
    target_id: str,
    relation_type: Optional[str] = None,
) -> Dict[str, object]:
    """Certain/possible answer for a relationship between two entities.

    Returns existence (does an edge hold in every / some repair) and the claim
    value (e.g. status = active|inactive). A contested group has **no certain
    claim** but lists all values as possible.
    """
    cs, ct = _canon(index, source_id), _canon(index, target_id)
    rt = relation_type.strip().lower() if relation_type else None

    matched = []
    claims: List[str] = []
    for r in index.relationships.values():
        if r.source == cs and r.target == ct and (
            rt is None or (r.relation_type or "").strip().lower() == rt
        ):
            matched.append(r)
            claim = r.attributes.get("claim")
            if claim is not None:
                claims.append(str(claim))

    exists = len(matched) > 0
    distinct = sorted(set(claims))
    contested = len(distinct) > 1
    return {
        "source": cs,
        "target": ct,
        "relation_type": relation_type,
        # the edge is present in every repair (each repair keeps one claim)
        "exists": {"certain": exists, "possible": exists},
        "claim": {
            "certain": [] if contested else distinct,  # contested -> no certain claim
            "possible": distinct,
        },
        "contested": contested,
        "sources": [
            {"id": r.id, "claim": r.attributes.get("claim"), "provenance": r.provenance.get("sources")}
            for r in matched
        ],
    }


def query_entity_type(index: SemanticIndex, name: str) -> Dict[str, object]:
    """Certain/possible type for entities sharing a (normalized) name.

    Same-name-but-distinct entities are *not* fused, so a name may denote several
    types across repairs — certain only if they all agree.
    """
    norm = util.normalize_name(name)
    types = sorted({
        e.type for e in index.entities.values()
        if util.normalize_name(e.name) == norm and e.type is not None
    })
    contested = len(types) > 1
    return {
        "name": name,
        "type": {"certain": [] if contested else types, "possible": types},
        "contested": contested,
    }


def list_conflicts(index: SemanticIndex) -> List[object]:
    """The preserved ConflictSets recorded on the merged index."""
    return list(index.metadata.get("conflicts", []))
