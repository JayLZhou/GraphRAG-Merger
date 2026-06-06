"""Cost metrics for a merge run.

Measures the resources the merge consumed, to contrast incremental merging with
a notional full rebuild:

  * **merge time**            — wall-clock seconds for the pipeline.
  * **bridge comparisons**    — number of entity pairs actually scored (tests
    the blocking claim: should be ``~ N_small * log N_large``, not quadratic).
  * **repair cost**           — summed estimated cost of the repair plan
    (proxy for LLM summary regenerations avoided).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostReport:
    merge_seconds: float
    bridge_comparisons: int
    repair_cost: float


def time_merge(merge_callable, *args, **kwargs):  # pragma: no cover
    """Run ``merge_callable(*args, **kwargs)``, returning ``(result, CostReport)``.

    Use ``time.perf_counter()`` for wall-clock; surface ``bridge_comparisons``
    and ``repair_cost`` via instrumentation hooks on the pipeline.
    """
    raise NotImplementedError("TODO(codex task 2): implement cost measurement")
