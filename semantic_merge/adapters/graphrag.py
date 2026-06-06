"""Adapter for Microsoft GraphRAG parquet outputs.

Loads a GraphRAG output directory (the ``*.parquet`` artifacts) into a
:class:`~semantic_merge.schema.SemanticIndex`, and writes a merged index back
out in a compatible layout. The mapping is tolerant of GraphRAG version
differences:

  * entity name comes from ``title`` (newer) or ``name`` (older);
  * relationship ``source``/``target`` may be entity *titles* (GraphRAG's usual
    form) or ids — both are resolved to entity ids;
  * community id is the integer ``community`` column when present (so community
    reports link up), falling back to the row ``id``;
  * missing optional columns are handled gracefully.

pandas/pyarrow are imported lazily here so the core package needs neither.
``pip install -e ".[graphrag]"`` to get them.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

from ..schema import (
    Community,
    Entity,
    Relationship,
    SemanticIndex,
    Summary,
    TextUnit,
)
from ..util import normalize_name

# Candidate filenames per artifact (newer short names first, older names second).
_FILES = {
    "entities": ["entities.parquet", "create_final_entities.parquet"],
    "relationships": ["relationships.parquet", "create_final_relationships.parquet"],
    "communities": ["communities.parquet", "create_final_communities.parquet"],
    "reports": ["community_reports.parquet", "create_final_community_reports.parquet"],
    "text_units": ["text_units.parquet", "create_final_text_units.parquet"],
}


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return False


def _get(rec: Dict[str, Any], *names: str, default: Any = None) -> Any:
    """First present, non-missing value among ``names``."""
    for n in names:
        if n in rec and not _is_missing(rec[n]):
            return rec[n]
    return default


def _as_list(v: Any) -> List[str]:
    """Coerce a parquet cell (None / NaN / list / ndarray / scalar) to list[str]."""
    if _is_missing(v):
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    if hasattr(v, "tolist"):
        return [str(x) for x in v.tolist()]
    return [str(v)]


def _read(path: str, names: List[str]):
    import pandas as pd  # lazy

    for name in names:
        fp = os.path.join(path, name)
        if os.path.exists(fp):
            return pd.read_parquet(fp)
    return None


def load_graphrag(path: str) -> SemanticIndex:
    """Load a GraphRAG output directory into a :class:`SemanticIndex`."""
    if not os.path.isdir(path):
        raise NotADirectoryError(f"{path!r} is not a GraphRAG output directory")

    index = SemanticIndex(name=os.path.basename(os.path.normpath(path)) or "graphrag")
    frames = {key: _read(path, names) for key, names in _FILES.items()}

    # ---- text units --------------------------------------------------------
    if frames["text_units"] is not None:
        for rec in frames["text_units"].to_dict("records"):
            tid = str(_get(rec, "id", "human_readable_id"))
            docs = _as_list(_get(rec, "document_ids", "document_id"))
            index.text_units[tid] = TextUnit(
                id=tid,
                text=str(_get(rec, "text", default="")),
                document_id=docs[0] if docs else None,
                n_tokens=_get(rec, "n_tokens"),
            )

    # ---- entities ----------------------------------------------------------
    title2id: Dict[str, str] = {}
    if frames["entities"] is not None:
        for rec in frames["entities"].to_dict("records"):
            eid = str(_get(rec, "id", "human_readable_id"))
            name = str(_get(rec, "title", "name", default=eid))
            ent = Entity(
                id=eid,
                name=name,
                type=_get(rec, "type"),
                description=_get(rec, "description"),
                text_unit_ids=_as_list(_get(rec, "text_unit_ids")),
                embedding=(_get(rec, "description_embedding")
                           if isinstance(_get(rec, "description_embedding"), (list, tuple)) else None),
                attributes={"human_readable_id": _get(rec, "human_readable_id")},
            )
            index.entities[eid] = ent
            title2id[normalize_name(name)] = eid

    entity_ids = set(index.entities)

    def _resolve(ref: Any) -> str:
        s = str(ref)
        if s in entity_ids:
            return s
        return title2id.get(normalize_name(s), s)

    # ---- relationships -----------------------------------------------------
    if frames["relationships"] is not None:
        for i, rec in enumerate(frames["relationships"].to_dict("records")):
            rid = str(_get(rec, "id", "human_readable_id", default=f"r{i}"))
            index.relationships[rid] = Relationship(
                id=rid,
                source=_resolve(_get(rec, "source")),
                target=_resolve(_get(rec, "target")),
                relation_type=_get(rec, "relation_type", "type"),
                description=_get(rec, "description"),
                weight=float(_get(rec, "weight", default=1.0)),
                text_unit_ids=_as_list(_get(rec, "text_unit_ids")),
            )

    # ---- communities -------------------------------------------------------
    def _resolve_members(refs: List[str]) -> List[str]:
        return [_resolve(r) for r in refs]

    if frames["communities"] is not None:
        for rec in frames["communities"].to_dict("records"):
            cid = str(_get(rec, "community", "id"))
            parent = _get(rec, "parent")
            index.communities[cid] = Community(
                id=cid,
                entity_ids=_resolve_members(_as_list(_get(rec, "entity_ids"))),
                relationship_ids=_as_list(_get(rec, "relationship_ids")),
                level=int(_get(rec, "level", default=0)),
                parent_id=(str(parent) if not _is_missing(parent) and str(parent) not in ("-1",) else None),
                children_ids=_as_list(_get(rec, "children", "children_ids")),
                title=_get(rec, "title"),
            )

    # ---- community reports -> summaries ------------------------------------
    if frames["reports"] is not None:
        for rec in frames["reports"].to_dict("records"):
            cid = str(_get(rec, "community", "id"))
            sid = str(_get(rec, "id", "human_readable_id", default=f"report-{cid}"))
            index.summaries[sid] = Summary(
                id=sid,
                community_id=cid,
                text=str(_get(rec, "summary", "full_content", "title", default="")),
                coverage=1.0,
            )

    return index


def save_graphrag(index: SemanticIndex, path: str) -> None:
    """Write a :class:`SemanticIndex` to ``path`` as GraphRAG-style parquet files.

    Endpoints are written as entity ids; :func:`load_graphrag` round-trips this
    layout. (It is a compatible subset, not a byte-for-byte GraphRAG rebuild.)
    """
    import pandas as pd  # lazy

    os.makedirs(path, exist_ok=True)

    def _write(name: str, rows: List[Dict[str, Any]]) -> None:
        pd.DataFrame(rows).to_parquet(os.path.join(path, name), index=False)

    _write("entities.parquet", [
        {"id": e.id, "title": e.name, "type": e.type, "description": e.description,
         "text_unit_ids": e.text_unit_ids, "aliases": e.aliases}
        for e in index.entities.values()
    ])

    _write("relationships.parquet", [
        {"id": r.id, "source": r.source, "target": r.target,
         "relation_type": r.relation_type, "description": r.description,
         "weight": r.weight, "text_unit_ids": r.text_unit_ids}
        for r in index.relationships.values()
    ])

    _write("communities.parquet", [
        {"id": c.id, "community": c.id, "level": c.level, "title": c.title,
         "entity_ids": c.entity_ids, "relationship_ids": c.relationship_ids,
         "parent": c.parent_id if c.parent_id is not None else "-1"}
        for c in index.communities.values()
    ])

    _write("community_reports.parquet", [
        {"id": s.id, "community": s.community_id, "title": s.attributes.get("title"),
         "summary": s.text}
        for s in index.summaries.values()
    ])

    _write("text_units.parquet", [
        {"id": t.id, "text": t.text, "n_tokens": t.n_tokens,
         "document_ids": [t.document_id] if t.document_id else []}
        for t in index.text_units.values()
    ])
