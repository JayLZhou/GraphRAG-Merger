"""Generate synthetic semantic indexes with planted, controllable phenomena.

The synthetic generator is what lets us measure merge quality without real
GraphRAG outputs. It plants known ground-truth phenomena so metrics are exact:

  * **duplicated entities**          — same real-world entity in both indexes;
  * **alias variations**             — "J. Smith" vs "John Smith";
  * **same-name different entities** — two distinct "Apple" (fruit vs company);
  * **relationship conflicts**       — contradictory edges on the same pair;
  * **temporal updates**             — a fact that changed over time;
  * **stale summaries**              — community summaries whose members shifted.

The generator should return the two indexes *and* a ground-truth record (which
entities are truly the same, which conflicts are planted) so evaluation can
compute precision/recall against truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from semantic_merge.schema import SemanticIndex


@dataclass
class GroundTruth:
    """Planted answers for an evaluation pair."""

    # canonical key -> entity ids (across both indexes) that truly co-refer
    duplicate_groups: Dict[str, List[str]] = field(default_factory=dict)
    # entity ids that share a name but are NOT the same entity
    same_name_distinct: List[Tuple[str, str]] = field(default_factory=list)
    # relationship id pairs that genuinely contradict
    relationship_conflicts: List[Tuple[str, str]] = field(default_factory=list)
    # community ids whose summaries should be stale after merge
    stale_summaries: List[str] = field(default_factory=list)


def build_synthetic_pair(
    n_entities: int = 100,
    overlap: float = 0.3,
    conflict_rate: float = 0.1,
    seed: int = 0,
) -> Tuple[SemanticIndex, SemanticIndex, GroundTruth]:
    """Build two synthetic indexes plus ground truth.

    Args:
        n_entities: approximate entity count of the larger index.
        overlap: fraction of entities shared (planted duplicates) between them.
        conflict_rate: fraction of shared entities given conflicting evidence.
        seed: RNG seed for reproducibility (use ``random.Random(seed)``).
    """
    raise NotImplementedError(
        "TODO(codex task 2): generate synthetic index pair with planted phenomena"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(
        "Not implemented yet — see docs/codex_tasks.md (task 2)."
    )
