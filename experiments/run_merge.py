"""Run and compare merge strategies on synthetic data.

Baselines:
  * **naive union**  — concatenate; no dedup, no reconciliation.
  * **name-only**    — fuse entities iff normalized names match exactly.
  * **semantic merge** — the full :func:`semantic_merge.merge_two_indexes` pipeline.

``python -m experiments.run_merge`` prints a comparison table over a synthetic
pair. Use ``--n``, ``--overlap``, ``--conflict-rate``, ``--seed`` to vary it.
"""

from __future__ import annotations

import os
import sys

# Support both `python -m experiments.run_merge` and `python experiments/run_merge.py`.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from collections import defaultdict
from typing import Dict, List

from experiments.eval_cost import CostReport, time_merge
from experiments.eval_index_quality import QualityReport, evaluate_quality
from experiments.make_synthetic_indexes import build_synthetic_pair
from semantic_merge import merge_two_indexes
from semantic_merge.schema import MergeConfig, RepairPlan, SemanticIndex
from semantic_merge.util import normalize_name


def _empty_meta(a: SemanticIndex, b: SemanticIndex, id_map: Dict[str, str]) -> dict:
    return {
        "id_map": id_map,
        "conflicts": [],
        "repair_plan": RepairPlan(decisions=[]),
        "affected_communities": [],
        "bridge_comparisons": 0,
    }


def naive_union_merge(a: SemanticIndex, b: SemanticIndex, config: MergeConfig) -> SemanticIndex:
    """Baseline: union all records with no dedup or reconciliation."""
    merged = SemanticIndex(name="naive_union")
    merged.text_units = {**b.text_units, **a.text_units}
    merged.entities = {**b.entities, **a.entities}
    merged.relationships = {**b.relationships, **a.relationships}
    merged.communities = {**b.communities, **a.communities}
    merged.summaries = {**b.summaries, **a.summaries}
    id_map = {e: e for e in merged.entities}
    merged.metadata = _empty_meta(a, b, id_map)
    return merged


def name_only_merge(a: SemanticIndex, b: SemanticIndex, config: MergeConfig) -> SemanticIndex:
    """Baseline: fuse entities only on exact normalized-name match (ignores type)."""
    # Group every entity id by normalized name; anchor canonical on the b side.
    by_name: Dict[str, List[str]] = defaultdict(list)
    owner: Dict[str, SemanticIndex] = {}
    for idx in (b, a):
        for e in idx.entities.values():
            by_name[normalize_name(e.name)].append(e.id)
            owner[e.id] = idx

    id_map: Dict[str, str] = {}
    merged = SemanticIndex(name="name_only")
    for _, ids in by_name.items():
        canonical = ids[0]  # b-side first (b iterated first)
        rep = owner[canonical].entities[canonical]
        merged.entities[canonical] = rep
        for i in ids:
            id_map[i] = canonical

    # remap + naively collapse edges (no conflict detection)
    for idx in (b, a):
        for r in idx.relationships.values():
            cs, ct = id_map.get(r.source, r.source), id_map.get(r.target, r.target)
            rid = f"{cs}|{ct}|{(r.relation_type or '').lower()}"
            merged.relationships[rid] = r  # later write wins (silent overwrite)
    merged.text_units = {**b.text_units, **a.text_units}
    merged.communities = {**b.communities}
    merged.summaries = {**b.summaries}
    merged.metadata = _empty_meta(a, b, id_map)
    return merged


_STRATEGIES = {
    "naive_union": naive_union_merge,
    "name_only": name_only_merge,
    "semantic": merge_two_indexes,
}


def run_all(n: int, overlap: float, conflict_rate: float, seed: int):
    small, large, gt = build_synthetic_pair(n, overlap, conflict_rate, seed)
    config = MergeConfig(namespace_ids=False)  # synthetic ids are already unique
    rows = []
    for name, fn in _STRATEGIES.items():
        merged, cost = time_merge(fn, small, large, config)
        rows.append((name, evaluate_quality(merged, gt), cost))
    return small, large, gt, rows


def _print_table(small, large, gt, rows) -> None:
    print(f"\nsmall={small.n_entities} entities, large={large.n_entities} entities | "
          f"planted: {len(gt.duplicate_groups)} dup groups, "
          f"{len(gt.same_name_distinct)} same-name-distinct, "
          f"{len(gt.relationship_conflicts)} edge conflicts\n")
    header = ["strategy", "dup_rate", "wrong_merge", "conflict_keep", "affected", "repaired", "compares", "seconds"]
    print("{:<13}{:>10}{:>13}{:>15}{:>10}{:>10}{:>10}{:>10}".format(*header))
    print("-" * 91)
    for name, q, c in rows:
        print("{:<13}{:>10.2f}{:>13.2f}{:>15.2f}{:>10}{:>10}{:>10}{:>10.4f}".format(
            name, q.entity_duplicate_rate, q.wrong_merge_rate,
            q.edge_conflict_preservation_rate, q.n_affected_communities,
            q.n_repaired_summaries, c.bridge_comparisons, c.merge_seconds))
    print("\nLower dup_rate/wrong_merge is better; higher conflict_keep is better.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare semantic index merge strategies.")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--overlap", type=float, default=0.3)
    ap.add_argument("--conflict-rate", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    small, large, gt, rows = run_all(args.n, args.overlap, args.conflict_rate, args.seed)
    _print_table(small, large, gt, rows)


if __name__ == "__main__":
    main()
