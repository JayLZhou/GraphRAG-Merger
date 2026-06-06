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

## Headline comparisons we expect to show

- Ours achieves **low duplicate rate AND high conflict preservation
  simultaneously** — the Pareto point neither baseline can reach (name-only gets
  one or the other depending on threshold; naive union gets neither).
- Repair cost and affected-community count grow with **planted overlap/conflict
  rate**, not with total index size — evidence of locality.

## Multi-index experiments (task 3)

Vary `k ∈ {2, 4, 8, 16}`. For each `k`, compare merge-order strategies
(`random`, `small_first`, `large_first`, `semantic_aware`) on total merge time
and final index quality. Expect `semantic_aware` ≈ best total cost, with the gap
over `random` widening as `k` grows.

## Reproducibility

- All randomness flows through a single seed (`random.Random(seed)`); no
  wall-clock or global RNG in the generator.
- No network and no LLM calls anywhere in the experiment path.
