"""Run and compare merge strategies on synthetic data.

Baselines to compare against the proposed semantic merge:

  * **naive union**  — concatenate both indexes; no dedup, no reconciliation.
  * **name-only**    — fuse entities iff normalized names match exactly.
  * **semantic merge** — the full :func:`semantic_merge.merge_two_indexes` pipeline.

This script ties :mod:`make_synthetic_indexes` to the evaluators in
:mod:`eval_index_quality` / :mod:`eval_cost` and prints a comparison table.
"""

from __future__ import annotations

from semantic_merge.schema import MergeConfig, SemanticIndex


def naive_union_merge(a: SemanticIndex, b: SemanticIndex, config: MergeConfig) -> SemanticIndex:
    """Baseline: union all records with no dedup or reconciliation."""
    raise NotImplementedError("TODO(codex task 2): implement naive union baseline")


def name_only_merge(a: SemanticIndex, b: SemanticIndex, config: MergeConfig) -> SemanticIndex:
    """Baseline: fuse entities only on exact normalized-name match."""
    raise NotImplementedError("TODO(codex task 2): implement name-only baseline")


def main() -> None:  # pragma: no cover
    raise SystemExit("Not implemented yet — see docs/codex_tasks.md (task 2).")


if __name__ == "__main__":  # pragma: no cover
    main()
