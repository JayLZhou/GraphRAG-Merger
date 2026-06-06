# Theory

> **Status: skeleton.** This file states the intended results and ties each to
> the module that realizes it. Formal definitions and proofs are filled in by
> Codex task 2 (see [`codex_tasks.md`](codex_tasks.md)). Keep notation concise;
> every theorem must name the module(s) it constrains.

Notation: `I = (T, E, R, C, S, P)` as in [`problem_definition.md`](problem_definition.md).
`N = |E|`. For a binary merge, `N_s = |E_small|`, `N_l = |E_large|`.

---

## 1. Semantic index, formally

Restate `I` and the merge operator with the four correctness invariants
(no-evidence-loss, conflict-preservation, referential integrity, temporal
monotonicity). Establish the equivalence relation `≡` (true co-reference) used
throughout.

*Module:* [`schema.py`](../semantic_merge/schema.py).

## 2. Oracle equivalence to full rebuild

**Claim.** Under an exact bridge oracle (a perfect `≡` classifier) and exact
edge reconciliation, the localized merge `merge(I_A, I_B)` produces an index
**equivalent** to `rebuild(T_A ∪ T_B)` *up to the affected region* — i.e. the
two indexes agree on all entities/edges and on every community outside the
affected region, and inside it after repair.

State the precise equivalence (graph-isomorphism on entities+edges modulo
canonical ids; agreement of community partition and summary coverage). Identify
the assumptions under which it holds and characterize the residual gap when the
oracle is approximate.

*Modules:* [`merge.py`](../semantic_merge/merge.py), [`affected_region.py`](../semantic_merge/affected_region.py).

## 3. Binary merge complexity

**Claim.** With blocking and forward search from the smaller index, bridge
discovery performs `O(N_s · log N_l)` (or `O(N_s · b)` with bounded block size
`b`) comparisons, versus `O(N_s · N_l)` for brute force. Fusion and edge
reconciliation are near-linear in the number of retained bridges and edges.

Define the blocking key and the bounded-candidate parameter `M`, and bound the
total work of the pipeline.

*Modules:* [`bridge.py`](../semantic_merge/bridge.py), [`prune.py`](../semantic_merge/prune.py).

## 4. Lazy reverse candidate preservation

**Claim.** Carrying large-index entities over verbatim while recording their
reverse candidacy preserves all true correspondences that a symmetric (two-way)
search would find, at no extra search cost — reverse candidates are resolved
on demand without a second `O(N_l · log N_s)` pass.

State what "preservation" means (no true bridge is lost) and why deferral is
safe given the invariants.

*Modules:* [`merge.py`](../semantic_merge/merge.py) (step 4), [`bridge.py`](../semantic_merge/bridge.py).

## 5. Conflict preservation invariant

**Claim.** The fusion + reconciliation procedure satisfies invariants (1) and
(2): for any contradictory pair of claims, both survive in `I_M` linked by a
conflict set; for any evidence record, it remains reachable in `I_M`.

Prove by structural induction over the merge steps that neither step can delete
evidence or collapse a contradiction.

*Modules:* [`entity_merge.py`](../semantic_merge/entity_merge.py), [`edge_reconcile.py`](../semantic_merge/edge_reconcile.py).

## 6. Affected region completeness

**Claim.** The set of communities returned by affected-region detection is a
**superset** of every community that a full rebuild would alter — i.e. detection
has no false negatives. Hence repairing only the affected region cannot leave a
stale community that a rebuild would have changed.

Define "altered community" and prove completeness (over-approximation allowed).

*Module:* [`affected_region.py`](../semantic_merge/affected_region.py).

## 7. Local repair planner optimality (independent communities)

**Claim.** When affected communities are independent (no shared entities/edges,
non-hierarchical), choosing per community the cheapest action satisfying
`drift ≤ τ` and `coverage ≥ κ` yields the **globally minimum-cost** repair plan
meeting those constraints.

Show the objective separates across communities, so greedy-per-community = global
optimum.

*Module:* [`repair_planner.py`](../semantic_merge/repair_planner.py).

## 8. Tree-DP extension (hierarchical communities)

**Claim.** When communities form a hierarchy (parent/child levels), per-community
greedy is no longer optimal because a parent rebuild subsumes child repairs. The
optimal plan is computed by **dynamic programming over the community tree**:
`cost(v) = min(repair_here(v), Σ_{c ∈ children(v)} cost(c))` with constraint
propagation for drift/coverage.

State the recurrence and its optimality; bound its `O(|C|)` runtime.

*Modules:* [`repair_planner.py`](../semantic_merge/repair_planner.py), [`schema.py`](../semantic_merge/schema.py) (`Community.parent_id`/`children_ids`).

## 9. Multi-index merge-order cost model

**Claim.** For `k` indexes, total merge cost depends on order. Define a
per-pair estimator

```
Ĉ(I_i, I_j) = c_alpha · N_s · log N_l
            + c_beta  · candidate_pairs
            + c_gamma · conflict_risk
            + c_delta · affected_communities
            + c_epsilon · summary_repair_cost
```

and benefit `Benefit(I_i, I_j) = overlap + duplicate_reduction`. Greedily merging
the pair minimizing `Ĉ / (1 + Benefit)` approximates the minimum-cost merge
schedule. Characterize when `small_first` / `semantic_aware` beat `random` /
`large_first`.

*Modules:* multi-index planner added in task 3 (`merge.merge_k_indexes`).

---

### Theorem → module map (summary)

| # | Result | Module(s) |
|---|--------|-----------|
| 1 | Index + invariants | `schema.py` |
| 2 | Oracle equivalence to rebuild | `merge.py`, `affected_region.py` |
| 3 | Binary merge complexity | `bridge.py`, `prune.py` |
| 4 | Lazy reverse preservation | `merge.py`, `bridge.py` |
| 5 | Conflict preservation | `entity_merge.py`, `edge_reconcile.py` |
| 6 | Affected-region completeness | `affected_region.py` |
| 7 | Local repair optimality | `repair_planner.py` |
| 8 | Tree-DP hierarchical repair | `repair_planner.py` |
| 9 | Multi-index order cost model | `merge_k_indexes` (task 3) |
