"""Core data model for graph-augmented RAG semantic indexes.

This module is the single source of truth for the data structures that flow
through the merge pipeline. It is intentionally dependency-free (pure standard
library) so the package is importable anywhere and easy to reason about.

A *semantic index* is the materialized output of a graph-augmented RAG build
(e.g. Microsoft GraphRAG). It bundles:

- ``TextUnit``      raw chunks the index was built from
- ``Entity``        nodes extracted from text units
- ``Relationship``  edges / claims between entities
- ``Community``     clusters of entities (possibly hierarchical)
- ``Summary``       materialized natural-language summaries of communities
- provenance metadata threaded through every record

The merge problem: given two such indexes, produce a single consistent index
without naively unioning (which duplicates entities and silently drops
conflicting evidence) and without paying for a full rebuild.

All result/config containers used across the pipeline live here too, so every
module shares one vocabulary and imports stay acyclic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

# A dense embedding vector. Kept as a plain list[float] so the core model has
# no hard numpy dependency; helpers may convert to numpy arrays internally.
Embedding = List[float]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RepairAction(str, Enum):
    """Repair actions a planner may take on an affected community region.

    Ordered cheapest -> most expensive. The planner chooses the cheapest
    action that brings drift below threshold and keeps coverage acceptable.
    """

    NOOP = "noop"
    PATCH_SUMMARY = "patch_summary"
    REGENERATE_SUMMARY = "regenerate_summary"
    LOCAL_RECLUSTER = "local_recluster"
    FULL_REGION_REBUILD = "full_region_rebuild"


class ConflictKind(str, Enum):
    """What two records disagree about when they cannot be safely fused."""

    SAME_NAME_DIFFERENT_ENTITY = "same_name_different_entity"
    CONTRADICTORY_RELATIONSHIP = "contradictory_relationship"
    INCOMPATIBLE_TYPE = "incompatible_type"
    TEMPORAL_CONFLICT = "temporal_conflict"
    AMBIGUOUS_BRIDGE = "ambiguous_bridge"


class BridgeConfidence(str, Enum):
    """Confidence tier assigned to a candidate entity bridge.

    HIGH bridges fuse; LOW bridges stay separate; AMBIGUOUS bridges are
    preserved as ambiguity records for later (lazy) resolution.
    """

    HIGH = "high"
    AMBIGUOUS = "ambiguous"
    LOW = "low"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


@dataclass
class TextUnit:
    """A chunk of source text an index was built from."""

    id: str
    text: str
    document_id: Optional[str] = None
    n_tokens: Optional[int] = None
    embedding: Optional[Embedding] = None
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class Entity:
    """A node in the semantic graph.

    ``text_unit_ids`` and ``provenance`` are the evidence trail; the merge
    pipeline must preserve and union them rather than overwrite.
    """

    id: str
    name: str
    type: Optional[str] = None
    description: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    text_unit_ids: List[str] = field(default_factory=list)
    embedding: Optional[Embedding] = None
    # Temporal validity, when the source provides it.
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Free-form provenance, e.g. {"index": "A", "source_ids": [...]}.
    provenance: Dict[str, object] = field(default_factory=dict)
    attributes: Dict[str, object] = field(default_factory=dict)


@dataclass
class Relationship:
    """A directed edge / claim between two entities."""

    id: str
    source: str  # endpoint Entity.id
    target: str  # endpoint Entity.id
    relation_type: Optional[str] = None
    description: Optional[str] = None
    weight: float = 1.0
    text_unit_ids: List[str] = field(default_factory=list)
    # Temporal stamps enable versioning of updated facts.
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    timestamp: Optional[str] = None
    provenance: Dict[str, object] = field(default_factory=dict)
    attributes: Dict[str, object] = field(default_factory=dict)


@dataclass
class Community:
    """A cluster of entities (and their internal edges).

    ``level`` and ``parent_id`` / ``children_ids`` support hierarchical
    community structure (Leiden-style), which the tree-DP repair extension
    relies on.
    """

    id: str
    entity_ids: List[str] = field(default_factory=list)
    relationship_ids: List[str] = field(default_factory=list)
    level: int = 0
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    title: Optional[str] = None
    attributes: Dict[str, object] = field(default_factory=dict)


@dataclass
class Summary:
    """A materialized natural-language summary of a community.

    ``source_hash`` lets the repair planner detect staleness: if the community
    membership changed since the summary was generated, the summary is stale.
    """

    id: str
    community_id: str
    text: str
    embedding: Optional[Embedding] = None
    coverage: float = 1.0  # fraction of community content reflected in summary
    source_hash: Optional[str] = None
    stale: bool = False
    attributes: Dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------


@dataclass
class SemanticIndex:
    """A complete graph-augmented RAG semantic index.

    Records are stored in id-keyed dicts for O(1) lookup. Helper accessors are
    provided; richer lookups (by name, by community) can be layered in
    ``loader.py`` or built lazily by callers.
    """

    name: Optional[str] = None
    text_units: Dict[str, TextUnit] = field(default_factory=dict)
    entities: Dict[str, Entity] = field(default_factory=dict)
    relationships: Dict[str, Relationship] = field(default_factory=dict)
    communities: Dict[str, Community] = field(default_factory=dict)
    summaries: Dict[str, Summary] = field(default_factory=dict)
    embedding_dim: Optional[int] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    # -- convenience accessors ------------------------------------------------

    @property
    def n_entities(self) -> int:
        return len(self.entities)

    @property
    def n_relationships(self) -> int:
        return len(self.relationships)

    def entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    def neighbors(self, entity_id: str) -> List[str]:
        """Return ids of entities adjacent to ``entity_id`` (either direction)."""
        out: List[str] = []
        for rel in self.relationships.values():
            if rel.source == entity_id:
                out.append(rel.target)
            elif rel.target == entity_id:
                out.append(rel.source)
        return out

    def add_entity(self, entity: Entity) -> None:
        self.entities[entity.id] = entity

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships[rel.id] = rel


# ---------------------------------------------------------------------------
# Bridge discovery / pruning result containers
# ---------------------------------------------------------------------------


@dataclass
class BridgeCandidate:
    """A scored candidate match between two entities across indexes.

    ``features`` records the individual signal scores (name, alias, type,
    embedding, neighbor, temporal) so pruning and fusion decisions are
    auditable rather than opaque.
    """

    source_id: str  # entity id in the (smaller) source index
    target_id: str  # entity id in the (larger) target index
    score: float
    confidence: BridgeConfidence = BridgeConfidence.LOW
    features: Dict[str, float] = field(default_factory=dict)


@dataclass
class EntityBridge:
    """A retained, accepted correspondence between two entities."""

    source_id: str
    target_id: str
    score: float
    confidence: BridgeConfidence
    features: Dict[str, float] = field(default_factory=dict)


@dataclass
class AmbiguitySet:
    """A preserved set of plausible-but-unresolved matches for one entity."""

    source_id: str
    candidates: List[BridgeCandidate] = field(default_factory=list)
    reason: ConflictKind = ConflictKind.AMBIGUOUS_BRIDGE


@dataclass
class BridgeResult:
    """Output of bridge discovery: scored candidates grouped per source entity."""

    candidates: List[BridgeCandidate] = field(default_factory=list)
    # source entity id -> its candidate matches, best first
    by_source: Dict[str, List[BridgeCandidate]] = field(default_factory=dict)


@dataclass
class PruneResult:
    """Output of robust pruning."""

    retained: List[BridgeCandidate] = field(default_factory=list)
    ambiguities: List[AmbiguitySet] = field(default_factory=list)
    conflicts: List[BridgeCandidate] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


@dataclass
class ConflictSet:
    """A group of records preserved *because* they conflict.

    The merge pipeline never silently overwrites evidence: when two records
    disagree, both are kept and recorded here for downstream resolution.
    """

    id: str
    kind: ConflictKind
    member_ids: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    resolved: bool = False
    attributes: Dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Repair planning result containers
# ---------------------------------------------------------------------------


@dataclass
class RepairDecision:
    """The chosen repair action for a single affected community."""

    community_id: str
    action: RepairAction
    drift: float
    estimated_cost: float
    coverage_after: Optional[float] = None
    rationale: Optional[str] = None


@dataclass
class RepairPlan:
    """The full set of per-community repair decisions for a merge."""

    decisions: List[RepairDecision] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(d.estimated_cost for d in self.decisions)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class MergeConfig:
    """All thresholds and weights controlling a merge.

    Defaults are reasonable starting points for synthetic experiments; tune
    per dataset. Grouped by pipeline stage.
    """

    # -- bridge discovery -----------------------------------------------------
    # Weights for combining individual similarity signals into a bridge score.
    w_name: float = 0.30
    w_alias: float = 0.15
    w_type: float = 0.10
    w_embedding: float = 0.30
    w_neighbor: float = 0.10
    w_temporal: float = 0.05
    # Minimum combined score for a pair to be considered a candidate at all.
    candidate_threshold: float = 0.5

    # -- pruning --------------------------------------------------------------
    # Keep at most M candidate bridges per source entity.
    max_candidates_per_entity: int = 5
    # Above -> HIGH (fuse); between -> AMBIGUOUS (preserve); below -> LOW.
    high_confidence_threshold: float = 0.85
    ambiguous_threshold: float = 0.65

    # -- repair planner: drift weights ---------------------------------------
    alpha: float = 0.30  # entity_change_ratio
    beta: float = 0.25   # edge_change_ratio
    gamma: float = 0.20  # boundary_change
    delta: float = 0.15  # conflict_density
    epsilon: float = 0.10  # summary_coverage_drop
    drift_threshold: float = 0.30
    coverage_threshold: float = 0.80

    # -- embeddings -----------------------------------------------------------
    use_embeddings: bool = True

    # -- multi-index planner cost weights (task 3) ---------------------------
    c_alpha: float = 1.0   # N_small * log(N_large)
    c_beta: float = 1.0    # candidate_pairs
    c_gamma: float = 1.0   # conflict_risk
    c_delta: float = 1.0   # affected_communities
    c_epsilon: float = 1.0  # summary_repair_cost

    # Misc knobs accessible to any stage without changing the signature.
    extra: Dict[str, object] = field(default_factory=dict)


__all__ = [
    "Embedding",
    "RepairAction",
    "ConflictKind",
    "BridgeConfidence",
    "TextUnit",
    "Entity",
    "Relationship",
    "Community",
    "Summary",
    "SemanticIndex",
    "BridgeCandidate",
    "EntityBridge",
    "AmbiguitySet",
    "BridgeResult",
    "PruneResult",
    "ConflictSet",
    "RepairDecision",
    "RepairPlan",
    "MergeConfig",
]
