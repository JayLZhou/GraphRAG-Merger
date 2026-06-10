# Problem Definition (v2): Compound Semantic Index Merging

> Formal statement for the SIGMOD framing. Narrative: [`idea.md`](idea.md).
> Algorithm: [`algorithm.md`](algorithm.md). Evaluation: [`evaluation.md`](evaluation.md).

## 1. Compound semantic index

**Definition 1 (Compound semantic index).** `I = (L, H, A, Z, P)` where

- **L** — typed low-level semantic units: chunks, entities `E`, relations
  `R ⊆ E×E`, claims;
- **H** — high-level organization: a DAG (typically a forest) of nodes over L
  with membership map `μ: E → 2^H`; root-to-leaf depth induces levels;
- **A** — materialized annotations `A: H ∪ L → Σ*` (community reports, cluster
  summaries, entity/relation descriptions); token-denominated;
- **Z** — retrieval structures: embedding maps and ANN indexes over L and A;
- **P** — provenance: `P: L →` source spans / document ids.

Algorithmic requirements: H acyclic with coverage (every `e ∈ E` reachable from
a root); A defined on the H-nodes used for routing. If `H = ∅` or `A = ∅`
(HippoRAG, fast-graphrag, LinearRAG), I is an `(L,Z,P)` instance and merging
degenerates to classical blocking+ER — in scope only as a degenerate baseline.

**Verified instantiations** (sources in [`related_work.md`](related_work.md)):

| Layer | MS GraphRAG | LightRAG | Youtu-GraphRAG |
|---|---|---|---|
| L | chunks, entities, relations, claims (parquet) | chunks, entities, relations (GraphML+JSON) | chunks, attributes, triples, keywords |
| H | multi-level Leiden community hierarchy | depth-1 dual-level keyword space | four-level knowledge tree |
| A | community reports per level | LLM entity/relation descriptions | LLM community summaries |
| Z | entity/report embeddings | nano-vectordb stores | FAISS caches |
| P | text-unit ids | source_id + file_path | chunk traceability |

## 2. The merge operator

**MERGE(I_s, I_t; Θ) → (I_m, B, X)** — out-of-place.

- *Inputs*: two independently built indexes over distinct, partially
  entity-overlapping corpora; no shared identifiers; **no access to raw corpora**.
- *Parameters Θ*: unified token budget `T`; window budgets `(B_e, B_token)`;
  per-entity bridge cap `M`; beam cap `L_max`; recall floor `ρ`; staleness bound
  `δ`; community policy `π_H ∈ {A: attach-only, B: local-recluster, C: full-recluster}`.
- *Outputs*: merged index `I_m`; bridge set `B` (§3); audit
  `X = (ambiguity sets, conflict sets, merge log)`.

## 3. Bridge set

**Definition 2 (Labeled bridges).**
`B ⊆ E_s × E_t × {certain, possible, cannot-link, conflict} × ℝ≥0` (evidence
weight), each pair tagged **verified** (co-resident in an examined ER window) or
**inferred**.

- **Pruning:** ≤ M bridges per source entity; pruning must retain ≥ 1
  representative of every label class present — ambiguity and conflict are
  preserved explicitly, never collapsed.
- **Consolidation:** union-find over *verified* certain edges under cannot-link
  constraints, with fixed precedence `cannot-link ≻ certain`: violating
  must-links are **downgraded to ambiguity, never force-merged**. Clusters
  connected only by cross-window chains are downgraded to *possible* unless one
  chain-endpoint pair is re-verified. Implied target–target merges (s certain to
  both t₁ and t₂) are enqueued for explicit verification, never auto-merged via
  a shared source.
- **Order-independence:** windows emit evidence only; resolution is one global
  pass; ties broken by evidence weight, then lexicographic id.

## 4. Routing: budgeted top-down search over H×A

State: frontier of pairs `(c_s, h)` — `c_s` any H_s node, `h` any H_t node
(level-agnostic), initialized at `roots(H_t)`. Actions: `descend(h → child)`,
`stop(h)` — spawning window `W(c_s, h) = (E(c_s), E(h))` with annotation
context — or `prune`. Constraints: `|E(W)| ≤ B_e`, `tok(W) ≤ B_token`.

- **Adaptive beam:**
  `L(c_s, h) = |{h′ ∈ ch(h) : sim(emb A(c_s), emb A(h′)) ≥ α·max_child}|`,
  capped at `L_max`.
- **Stopping rule:** descend while some child holds ≥ τ of the ANN-hit mass of
  `E(c_s)`; stop at the deepest node satisfying `B_e` whose window still
  contains all top-k ANN hits of every `e ∈ E(c_s)` (**per-window recall
  certificate**).
- **Hybrid fallback:** candidate pairs from name-ngram + embedding-ANN blocking
  not covered by any routed window are assigned to fallback windows — the
  hybrid candidate set **⊇** the flat ANN set (certified floor ρ).

Routing spends embedding comparisons only; LLM tokens are spent solely inside
stopped windows.

## 5. Objective: one unified merge-time token budget

```
tok(MERGE) = tok_ER (window calls + chain/implied-pair re-verifications)
           + tok_repair (annotation repair)

minimize tok(MERGE)  subject to:
  I1 (no evidence loss)       every unit of L_s ∪ L_t survives, possibly merged,
                              with audit trail
  I2 (referential integrity)  no dangling edges; endpoints remapped
  I3 (provenance)             P_m restricted to either input equals the original;
                              merged units take provenance unions
  I4 (conflict preservation)  no forced resolution; no cannot-link violated in I_m
  I5 (bounded staleness)      every annotation whose member set changed is
                              repaired or stale-flagged; unrepaired affected mass ≤ δ
  Recall floor                bridge recall ≥ ρ via the hybrid certificate
```

Community partition quality (NMI vs recluster, modularity) is explicitly a
**soft quality-cost knob** via `π_H` — reported on a Pareto curve, neither
optimized nor an invariant. One controller allocates T across the two terms:
routing minimizes `tok_ER`; tree-DP minimizes `tok_repair`; both priced by a
single token cost model ([`schema.py CostModel`](../semantic_merge/schema.py)).

## 6. Statements to prove

**Theorem 1 (Consolidation soundness and confluence).** For any window-emitted
evidence multiset, consolidation (i) violates no cannot-link; (ii) outputs
equivalence classes refining some clustering feasible w.r.t. all verified
evidence — hence every certain answer over I_m is a certain answer over every
evidence-consistent merge (**one-sided error**: over-segmentation loses certain
answers but never fabricates them); (iii) is a pure function of the evidence
multiset, invariant to window order. *Note:* minimizing disagreements under
must/cannot-links is correlation clustering — NP-hard (Bansal–Blum–Chawla) and
APX-hard (Charikar–Guruswami–Wirth); we claim soundness, not approximation;
over-segmentation is the safe direction precisely because of certain/possible
query semantics.

**Theorem 2 (Routing cost bound and hybrid dominance).** With beam cap `L_max`,
branching `b`, target hierarchy size `N_t`: routing performs
`O(n_s·L_max·b·log N_t)` embedding comparisons and spawns ≤ `n_s·L_max` routed
windows, so `tok_ER ≤ n_s·L_max·B_token + tok_fallback + tok_reverify`; and the
hybrid candidate set contains the flat ANN-blocking set, so hybrid bridge
recall ≥ ANN-blocking recall.

**Lemma 3 (Affected-region completeness).** Let `touched(B)` be entities
merged, re-described, or with changed incident edges. The upward closure R of
`μ(touched(B))` in H_m contains every node whose member or incident-edge
multiset differs from I_t; for `h ∉ R`, `A_t(h)` remains exact, so NOOP outside
R incurs zero staleness.

**Lemma 4 (Repair-plan optimality).** Under an additive token cost model on
tree-structured H_m, tree-DP over per-node actions {NOOP, PATCH, COMPOSE,
REGENERATE, LOCAL_RECLUSTER, FULL_REBUILD} returns a minimum-token plan among
all plans satisfying I5 with bound δ and parent–child action compatibility
(e.g., COMPOSE requires fresh child summaries).

---

## Appendix: v1 cost-model results (carried forward)

The token cost model and locality measurements from the v1 formulation remain
the basis of `tok_repair`:

```
cost(NOOP)      = 0
cost(PATCH)     = overhead + σ + p·out
cost(COMPOSE)   = overhead + Σ child-summary tokens + out     (reuse, no raw text)
cost(REGEN)     = overhead + T_content + out
cost(RECLUSTER) = n_sub·(overhead + out) + T_content
cost(REBUILD)   = overhead + (1 + ρ_extract)·T_content + out
```

Actions are **not** cost-ordered (RECLUSTER can exceed REBUILD for small
communities), so planners minimize cost over the feasible set. Synthetic
measurement (N = 200): merge repair = **11% / 34% / 43%** of full rebuild at
overlap 0.15 / 0.30 / 0.50; tree-DP ≈ **49%** of per-community greedy on
hierarchical data.
