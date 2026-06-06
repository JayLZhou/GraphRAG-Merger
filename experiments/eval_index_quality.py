"""Index-quality metrics for a merged index, scored against ground truth.

Metrics (lower is better unless noted):

  * **entity duplicate rate**          — fraction of true-duplicate groups left
    un-fused in the merged index.
  * **edge conflict preservation rate** (higher is better) — fraction of
    planted relationship conflicts retained as conflict sets rather than
    silently overwritten.
  * **number of affected communities** — size of the region the merge touched.
  * **number of repaired summaries**   — how many summaries needed PATCH/REGEN.

These let us show the proposed merge dominates the baselines: low duplicate
rate *and* high conflict preservation, which naive/name-only cannot achieve
simultaneously.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.make_synthetic_indexes import GroundTruth
from semantic_merge.schema import SemanticIndex


@dataclass
class QualityReport:
    entity_duplicate_rate: float
    edge_conflict_preservation_rate: float
    n_affected_communities: int
    n_repaired_summaries: int


def evaluate_quality(merged: SemanticIndex, truth: GroundTruth) -> QualityReport:
    """Score ``merged`` against planted ``truth``."""
    raise NotImplementedError("TODO(codex task 2): implement quality metrics")
