"""Loading and (de)serialization of semantic indexes.

Phase 1 targets a simple JSON representation so synthetic indexes round-trip
without external dependencies. A GraphRAG parquet adapter is intentionally
deferred (see ``docs/codex_tasks.md``, task 4) to keep the first version
self-contained.
"""

from __future__ import annotations

from typing import Union

from .schema import SemanticIndex


def load_index_from_json(path: Union[str, "os.PathLike[str]"]) -> SemanticIndex:  # noqa: F821
    """Load a :class:`SemanticIndex` from a JSON file.

    The JSON layout mirrors the dataclasses in :mod:`semantic_merge.schema`
    (one list per record type). Implementations should be tolerant of missing
    optional fields.
    """
    raise NotImplementedError("TODO(codex task 1): implement JSON index loading")


def save_index_to_json(index: SemanticIndex, path: Union[str, "os.PathLike[str]"]) -> None:  # noqa: F821
    """Serialize a :class:`SemanticIndex` to a JSON file (round-trips with load)."""
    raise NotImplementedError("TODO(codex task 1): implement JSON index saving")
