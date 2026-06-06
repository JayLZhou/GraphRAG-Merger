"""Multi-index merge-order experiment (docs/theory.md §9).

For each ``k`` and each ordering strategy, merge ``k`` overlapping shards into
one and report total cost (bridge comparisons, wall-clock) and final quality
(entity count vs. the ideal ``universe`` size). The merge *order* changes total
cost; ``semantic_aware`` should be at/near the cheapest while reaching the same
dedup quality.

``python -m experiments.run_multi_merge``
"""

from __future__ import annotations

import os
import sys

# Support both `python -m experiments.run_multi_merge` and direct execution.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from typing import List

from experiments.make_synthetic_indexes import build_synthetic_k
from semantic_merge import merge_k_indexes
from semantic_merge.schema import MergeConfig

_STRATEGIES = ["random", "small_first", "large_first", "semantic_aware"]


def run(ks: List[int], universe: int, appear_prob: float, seed: int) -> None:
    config = MergeConfig()  # namespacing ON: shards intentionally reuse ids
    print(f"\nuniverse={universe} distinct entities, appear_prob={appear_prob}\n")
    header = ["k", "strategy", "final_ents", "input_ents", "comparisons", "seconds"]
    print("{:<5}{:<16}{:>12}{:>12}{:>13}{:>10}".format(*header))
    print("-" * 68)
    for k in ks:
        indexes, ideal = build_synthetic_k(k=k, universe=universe, appear_prob=appear_prob, seed=seed)
        input_ents = sum(i.n_entities for i in indexes)
        for strategy in _STRATEGIES:
            start = time.perf_counter()
            final = merge_k_indexes(list(indexes), config, strategy=strategy, seed=seed)
            secs = time.perf_counter() - start
            print("{:<5}{:<16}{:>12}{:>12}{:>13}{:>10.4f}".format(
                k, strategy, final.n_entities, input_ents,
                final.metadata["total_bridge_comparisons"], secs))
        print("-" * 68)
    print(f"\nideal final entity count ~= {universe} (perfect dedup). "
          "Lower comparisons/seconds at equal final_ents is better.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare multi-index merge-order strategies.")
    ap.add_argument("--ks", type=int, nargs="+", default=[2, 4, 8, 16])
    ap.add_argument("--universe", type=int, default=60)
    ap.add_argument("--appear-prob", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run(args.ks, args.universe, args.appear_prob, args.seed)


if __name__ == "__main__":
    main()
