"""Cost metrics for a merge run.

  * **merge_seconds**      — wall-clock for the pipeline.
  * **bridge_comparisons** — entity pairs actually scored (tests the blocking
    claim: ``~ N_small * log N_large`` rather than the quadratic product).
  * **repair_cost**        — summed estimated cost of the repair plan (proxy for
    the LLM summary regenerations a full rebuild would have paid).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Tuple

from semantic_merge.schema import RepairPlan, SemanticIndex


@dataclass
class CostReport:
    merge_seconds: float
    bridge_comparisons: int
    repair_cost: float


def cost_of(merged: SemanticIndex) -> Tuple[int, float]:
    """Extract (bridge_comparisons, repair_cost) from a merged index's metadata."""
    comparisons = int(merged.metadata.get("bridge_comparisons", 0))
    plan: RepairPlan = merged.metadata.get("repair_plan")
    repair_cost = plan.total_cost if plan is not None else 0.0
    return comparisons, repair_cost


def time_merge(merge_callable: Callable[..., SemanticIndex], *args: Any, **kwargs: Any) -> Tuple[SemanticIndex, CostReport]:
    """Run ``merge_callable(*args, **kwargs)`` and return ``(result, CostReport)``."""
    start = time.perf_counter()
    result = merge_callable(*args, **kwargs)
    elapsed = time.perf_counter() - start
    comparisons, repair_cost = cost_of(result)
    return result, CostReport(merge_seconds=elapsed, bridge_comparisons=comparisons, repair_cost=repair_cost)
