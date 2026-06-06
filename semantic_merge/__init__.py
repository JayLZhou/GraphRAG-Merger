"""semantic_merge — efficient semantic index merging for graph-augmented RAG.

Public API. Most algorithmic functions are scaffolded with ``NotImplementedError``
and are implemented incrementally (see ``docs/codex_tasks.md``). The data model in
``schema`` is complete and importable today.
"""

from __future__ import annotations

from . import (
    affected_region,
    bridge,
    edge_reconcile,
    entity_merge,
    loader,
    merge,
    prune,
    repair_planner,
    schema,
)
from .merge import merge_two_indexes
from .schema import (
    AmbiguitySet,
    BridgeCandidate,
    BridgeConfidence,
    BridgeResult,
    Community,
    ConflictKind,
    ConflictSet,
    Entity,
    EntityBridge,
    MergeConfig,
    PruneResult,
    Relationship,
    RepairAction,
    RepairDecision,
    RepairPlan,
    SemanticIndex,
    Summary,
    TextUnit,
)

__version__ = "0.0.1"

__all__ = [
    # submodules
    "schema",
    "loader",
    "bridge",
    "prune",
    "entity_merge",
    "edge_reconcile",
    "affected_region",
    "repair_planner",
    "merge",
    # entrypoint
    "merge_two_indexes",
    # data model
    "TextUnit",
    "Entity",
    "Relationship",
    "Community",
    "Summary",
    "SemanticIndex",
    "BridgeCandidate",
    "EntityBridge",
    "BridgeResult",
    "AmbiguitySet",
    "PruneResult",
    "ConflictSet",
    "ConflictKind",
    "BridgeConfidence",
    "RepairAction",
    "RepairDecision",
    "RepairPlan",
    "MergeConfig",
]
