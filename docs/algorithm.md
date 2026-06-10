# Algorithm Specification (v2, post-critique)

> The refined end-to-end algorithm, incorporating the adversarial-review fixes
> (G1–G8). Formal statement: [`problem_definition.md`](problem_definition.md).

## 0. Preliminaries

A **compound semantic index** is `I = (L, H, A, Z, P)` (Definition 1).
**MERGE(I_s, I_t) → I_m** is out-of-place, conflict-tolerant, and runs under
**one unified token budget** `T = T_ER + T_verify + T_repair`, allocated by a
single controller: routing minimizes `T_ER`, tree-DP minimizes `T_repair`.

**Adapter contract:** a system instantiates the pipeline by supplying (H as a
DAG, A as a coverage function over L, `sim` over A, ANN over Z). If `H=∅` or
`A=∅` (HippoRAG), routing degrades to the safety net alone — classical
blocking+ER, by design.

## 1. Generic 9-step flow

**Step 1 — Load & normalize.** Adapters map both indexes into the shared
schema; provenance ids preserved verbatim.

**Step 2 — Hybrid routing.**
(a) *Annotation-guided descent*: route each source community top-down through
the target's H, comparing annotation embeddings, with adaptive beam `L`
(children with sim ≥ α·max, capped `L_max`).
(b) *Safety net*: cheap name-ngram + embedding-ANN blocking over raw L-units;
any candidate pair not co-resident in a routed window gets a fallback window.
Hybrid candidate set ⊇ ANN set by construction (dominance, Theorem 2).
Report **RR@cost** = gold bridge pairs co-resident in some examined window /
gold pairs, vs cumulative tokens.

**Step 3 — Window readiness (principled stopping).** Descend while one child
holds ≥ τ of the ANN-hit mass; stop at the deepest H-node fitting `B_e`
entities / `B_token` tokens **whose window still contains all top-k ANN hits of
the routed source entities** (per-window recall certificate). Oversized leaves
split by budget. Token bound: ≤ `n_s · L · B_token` merge-time ER tokens.

**Step 4 — In-window LLM-CER labeling.** Each window (source units + co-located
target units + their annotations) goes to LLM set clustering. **Output
contract** per pair: label ∈ {certain, possible, cannot-link, conflict},
evidence = (window id, provenance ids, score, rationale hash). Windows **emit
evidence only — never apply merges** (fixes order-dependence, G5). A
deterministic surrogate (string/embedding scorer) substitutes for record/replay
reproducibility.

**Step 5 — Robust pruning.** Per source entity keep top-M bridges by evidence
weight, but **never prune the last witness of an ambiguity or conflict set** —
certain-answer semantics over the pruned representation must match the unpruned
one (RQ4 invariant).

**Step 6 — Lazy backward + global consolidation.** Lazy pass touches only
target entities referenced by surviving bridges:
(i) *implied target–target pairs* (s certain to t1 and t2) are enqueued for
explicit verification — never auto-merged (G3);
(ii) *cross-window chains* (a~b in W1, b~c in W2, a,c never co-verified) are
flagged: chain-only clusters downgrade to *possible* unless one endpoint check
confirms (G2).
Then global union-find with cannot-link constraints, fixed precedence
`cannot-link > certain > possible`, ties by weight then id. Violations
**downgrade to AmbiguitySets — never force-merge**. Guarantees: **soundness**
(output refines a feasible clustering; over-segmentation is the safe one-sided
error under certain/possible querying) and **confluence** (output is a pure
function of the evidence multiset).

**Step 7 — Out-of-place conflict-tolerant merge.** Fuse L: union-find clusters
become merged entities with provenance-union; AmbiguitySets/ConflictSets
materialized, evidence never lost. Edges: remap endpoints, merge compatible,
version temporal updates, preserve contradictory claims as conflict sets. Z
rebuilt incrementally for touched units only.

**Step 8 — Affected-region detection + maintenance policy.** Compute H-nodes
whose membership changed (upward closure — Lemma 3). Apply the explicit
quality-cost knob: **Policy A** attach-only, **B** local recluster of affected
regions, **C** full recluster. Not a contribution; an eval axis (RQ5).

**Step 9 — Bottom-up annotation repair.** Tree-DP over affected H-nodes
chooses per-node among {NOOP, PATCH, COMPOSE, REGENERATE, LOCAL_RECLUSTER,
FULL_REBUILD} under the **residual budget** `T − T_ER − T_verify`, using the
token-grounded CostModel (Lemma 4 optimality; measured ~49% of greedy).

## 2. Pseudocode

```text
ROUTE(src_comms, H_t, A_t, B_e, B_tok, L_max, α, τ, k):
  W ← ∅
  for c_s in src_comms:
    frontier ← {root(H_t)}
    while frontier:
      n ← pop(frontier)
      beam ← {c ∈ children(n): sim(A[c_s],A[c]) ≥ α·max_sim}[:L_max]
      for c in beam:
        if fits(c,B_e,B_tok) and contains_topk_ANN(c, units(c_s), k):
          W ← W ∪ {window(c_s, c)}            # recall certificate holds
        elif mass(c) ≥ τ: push(frontier, c)    # keep descending
        else: W ← W ∪ {budget_split(c_s, n)}   # stop at parent
  for (u,v) ∈ ANN_or_ngram_pairs not co-resident in any W:
    W ← W ∪ {fallback_window(u, v)}            # safety net (dominance)
  return W

CONSOLIDATE(E):              # E = evidence multiset from all windows
  E ← canonical_sort(E)      # precedence: cannot > certain > possible; weight; id
  UF ← ∅; CL ← cannot_links(E); Q ← ∅
  for (u,v,certain,w) in E:
    if violates_CL(UF,u,v,CL): emit AmbiguitySet(u,v)      # never force-merge
    elif chain_only(u,v): mark_possible(u,v); Q ← Q ∪ {(u,v)}
    else: union(UF,u,v)
  for (t1,t2) implied via shared source: Q ← Q ∪ {(t1,t2)}  # G3
  verify(Q, budget=T_verify); unverified → possible
  return clusters(UF), ambiguity_sets, conflict_sets
```

## 3. Microsoft GraphRAG instantiation

L = entities/relationships/claims/text_units parquet; H = Leiden community
hierarchy; A = community reports; Z = embeddings; P = text_unit ids. Routing
descends the report tree by report-embedding similarity (`B_e` ≈ 30–50
entities, `B_token` ≈ 4–8k, `L_max` ≈ 3); windows carry entity descriptions +
parent report excerpts as ER context. Policy A = attach to nearest community;
B = local Leiden on affected regions; C = full Leiden. Repair = tree-DP over
the report tree.

**LightRAG instantiation:** depth-1 H (dual keyword space) ⇒ routing is
one-level windowing over keyword/description keys — graceful degradation with a
*predicted, measurable* cost delta (this is what makes the abstraction
load-bearing rather than cosmetic).

## 4. Design-gap fixes incorporated (from adversarial review)

| Gap | Fix |
|---|---|
| G1 ANN blocking is also sublinear | Comparison axis = tokens/LLM-calls per recovered bridge **at matched recall**; routing's win = bounded LLM context + zero extra index build |
| G2 unverified transitive merges across windows | verified vs inferred edges; chain-only clusters → possible unless endpoint re-verified |
| G3 implied target–target merges | enqueue for explicit verification; never auto-merge via shared source |
| G4 correlated routing failures (report blind spots, vocab mismatch, tail entities) | hybrid safety net (dominance by construction) + adaptive beam |
| G5 order-dependent lazy consolidation | windows emit evidence only; one global pass; fixed precedence → confluence |
| G6 ad-hoc stopping | monotonicity-based rule + per-window recall certificate |
| G7 consolidation hardness | correlation clustering NP/APX-hard; claim soundness (one-sided error), not approximation |
| G8 unified budget unspecified | `T = T_ER + T_verify + T_repair`, one controller, one cost model |

## 5. Module mapping (repo)

| Step | Existing (`semantic_merge/`) | New |
|---|---|---|
| 1 Load | `loader.py`, `schema.py`, `adapters/graphrag.py` | `adapters/lightrag.py`, `adapters/youtu.py` |
| 2 Routing | `bridge.py` blocking signals → safety net | **`router.py`** (descent, beam, certificates) |
| 3 Windows | — | **`windows.py`** (budgets, splitting) |
| 4 CER | `bridge.py` multi-signal scorer → surrogate | **`cer.py`** (LLM iface + deterministic surrogate + replay cache) |
| 5 Prune | `prune.py` (extend: ambiguity/conflict-witness preservation) | — |
| 6 Consolidate | `entity_merge.py` union-find, Ambiguity/ConflictSets | **`consolidate.py`** (evidence log, precedence, chain/implied-pair queues) |
| 7 Merge | `entity_merge.py`, `edge_reconcile.py` | — |
| 8 Regions/H | `affected_region.py`, `partition_reconcile.py` (Policy A) | Policy B/C hooks |
| 9 Repair | `repair_planner.py` (tree-DP), `query.py` (certain/possible) | **`budget.py`** (unified T controller) |
