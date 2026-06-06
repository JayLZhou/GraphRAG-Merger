# Experiments

Goal: validate, **offline and deterministically**, that the proposed semantic
merge (a) preserves correctness invariants, (b) reduces entity duplication while
preserving conflicts, and (c) costs far less than a full rebuild — and that the
multi-index planner picks good merge orders.

## Data: synthetic semantic indexes

We generate index pairs with **planted, known-truth phenomena** so every metric
is exact (no human labeling). Generator:
[`../experiments/make_synthetic_indexes.py`](../experiments/make_synthetic_indexes.py).

Planted phenomena:

| Phenomenon | What it stresses |
|---|---|
| duplicated entities | fusion recall |
| alias variations ("J. Smith" / "John Smith") | multi-signal bridging |
| same-name different entities ("Apple" co. / fruit) | fusion precision |
| relationship conflicts | conflict preservation |
| temporal updates | edge versioning |
| stale summaries | affected-region detection + repair |

The generator returns `(I_A, I_B, GroundTruth)`; `GroundTruth` records the true
duplicate groups, the same-name-distinct pairs, the planted conflicts, and which
community summaries should become stale.

## Baselines

1. **naive union** — concatenate; no dedup, no reconciliation.
2. **name-only** — fuse iff normalized names match exactly.
3. **semantic merge** (ours) — full pipeline.

Runner: [`../experiments/run_merge.py`](../experiments/run_merge.py).

## Metrics

Quality ([`eval_index_quality.py`](../experiments/eval_index_quality.py)):

- **entity duplicate rate** — fraction of true duplicate groups left un-fused
  (lower better). Naive union ≈ overlap fraction; ours should be ≈ 0.
- **edge conflict preservation rate** — fraction of planted conflicts retained
  as conflict sets (higher better). Naive/name-only typically lose these; ours
  should be ≈ 1.0.
- **number of affected communities** — locality of the disturbance.
- **number of repaired summaries** — how many PATCH/REGEN actions fired.

Cost ([`eval_cost.py`](../experiments/eval_cost.py)):

- **merge time** (wall-clock).
- **bridge comparisons** — should track `N_s · log N_l`, not `N_s · N_l`.
- **repair cost** — proxy for LLM regenerations avoided vs full rebuild.

## Headline comparison (observed)

`python -m experiments.run_merge --n 200 --overlap 0.4 --conflict-rate 0.3`:

```
strategy       dup_rate  wrong_merge  conflict_keep  affected  repaired  compares
naive_union        1.00         0.00           0.00         0         0         0
name_only          0.60         1.00           0.00         0         0         0
semantic           0.00         0.00           1.00        25        23      5089
```

- The semantic merge achieves **low duplicate rate AND low wrong-merge rate AND
  high conflict preservation simultaneously** — the Pareto point neither baseline
  reaches. Naive union fuses nothing (duplicate rate 1.0); name-only misses
  alias-variation duplicates (≈0.6) *and* wrongly fuses same-name-different
  entities (wrong-merge 1.0), and neither baseline preserves a single conflict.
- `compares` (≈5k) is well under the `N_small · N_large` brute-force product
  (≈20k here), confirming the blocking claim.
- Results are stable across seeds; raise `--conflict-rate` to stress conflict
  preservation, `--overlap` to stress fusion.

## Multi-index experiments (observed)

`python -m experiments.run_multi_merge` varies `k ∈ {2, 4, 8, 16}` and compares
`random`, `small_first`, `large_first`, `semantic_aware` on total bridge
comparisons, wall-clock, and final entity count (vs. the ideal `universe` size).

Observed: merge **order affects both total comparisons and final dedup quality**;
`semantic_aware` is consistently *among* the cheapest on comparisons and reaches
dedup quality at least as good as the baselines. The effect is real but modest
at this scale — total work is partly conserved because every duplicate must be
reconciled eventually regardless of order — and `semantic_aware` pays an
`O(k²)`-per-round estimator overhead that shows up in wall-clock at `k = 16`. A
larger, more size-skewed universe widens the order-sensitivity gap.

## Reproducibility

- All randomness flows through a single seed (`random.Random(seed)`); no
  wall-clock or global RNG in the generator.
- No network and no LLM calls anywhere in the experiment path.
