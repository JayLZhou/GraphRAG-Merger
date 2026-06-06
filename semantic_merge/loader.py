"""Loading and (de)serialization of semantic indexes.

Phase 1 uses a simple JSON representation that mirrors the dataclasses in
:mod:`semantic_merge.schema`, so synthetic indexes round-trip with no external
dependencies. A GraphRAG parquet adapter is intentionally deferred (see
``docs/codex_tasks.md`` task 4).
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, List, Type, TypeVar, Union

from .schema import (
    Community,
    Entity,
    Relationship,
    SemanticIndex,
    Summary,
    TextUnit,
)

PathLike = Union[str, "os.PathLike[str]"]

_T = TypeVar("_T")


def _rows(cls: Type[_T], records: List[dict]) -> Dict[str, _T]:
    """Reconstruct id-keyed dataclass instances, ignoring unknown fields."""
    fields = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    out: Dict[str, _T] = {}
    for rec in records:
        kept = {k: v for k, v in rec.items() if k in fields}
        obj = cls(**kept)  # type: ignore[call-arg]
        out[obj.id] = obj  # type: ignore[attr-defined]
    return out


def index_to_dict(index: SemanticIndex) -> dict:
    """Plain-dict view of an index (JSON-serializable)."""
    return {
        "name": index.name,
        "embedding_dim": index.embedding_dim,
        "metadata": index.metadata,
        "text_units": [dataclasses.asdict(x) for x in index.text_units.values()],
        "entities": [dataclasses.asdict(x) for x in index.entities.values()],
        "relationships": [dataclasses.asdict(x) for x in index.relationships.values()],
        "communities": [dataclasses.asdict(x) for x in index.communities.values()],
        "summaries": [dataclasses.asdict(x) for x in index.summaries.values()],
    }


def index_from_dict(data: dict) -> SemanticIndex:
    """Inverse of :func:`index_to_dict`."""
    return SemanticIndex(
        name=data.get("name"),
        embedding_dim=data.get("embedding_dim"),
        metadata=data.get("metadata", {}) or {},
        text_units=_rows(TextUnit, data.get("text_units", [])),
        entities=_rows(Entity, data.get("entities", [])),
        relationships=_rows(Relationship, data.get("relationships", [])),
        communities=_rows(Community, data.get("communities", [])),
        summaries=_rows(Summary, data.get("summaries", [])),
    )


def load_index_from_json(path: PathLike) -> SemanticIndex:
    """Load a :class:`SemanticIndex` from a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        return index_from_dict(json.load(fh))


def save_index_to_json(index: SemanticIndex, path: PathLike) -> None:
    """Serialize a :class:`SemanticIndex` to a JSON file (round-trips with load)."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(index_to_dict(index), fh, indent=2, ensure_ascii=False)
