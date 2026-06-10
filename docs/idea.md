# Idea v2: Compound Semantic Index Merging for Graph-Augmented RAG

> Supersedes the v1 framing (conflict-tolerant merge as headline, tree-DP as star).
> v1 survives intact as the **execution layer** of v2 — see "Where v1 lives now."

## One-line

**Semantic index merging is a new data-management primitive**: merging two
independently built graph-augmented-RAG indexes by **reusing their already-paid-for
high-level annotations (community reports / summaries) as a navigable merge-time
routing index** that localizes LLM-based bridge construction into small budgeted
windows — under **one unified merge-time token budget** covering bridge
construction *and* annotation repair.

## The abstraction

A **compound semantic index** is `I = (L, H, A, Z, P)`:

| Layer | Meaning | MS GraphRAG | LightRAG | Youtu-GraphRAG |
|---|---|---|---|---|
| **L** | low-level semantic units | chunks, entities, relations, claims | chunks, entities, relations | chunks, attributes, triples, keywords |
| **H** | high-level organization (DAG) | multi-level Leiden hierarchy | depth-1 dual keyword space | four-level knowledge tree |
| **A** | materialized annotations | community reports | entity/relation descriptions | community summaries |
| **Z** | retrieval structures | embeddings (LanceDB) | nano-vectordb stores | FAISS caches |
| **P** | provenance | text-unit ids | source_id + file_path | chunk traceability |

Honesty clause that *sharpens* the formulation: systems with `H=∅, A=∅`
(HippoRAG, fast-graphrag, LinearRAG) are `(L,Z,P)` instances — for them merging
*provably degenerates* to classical blocking+ER. H/A-guided merging applies
exactly when the system materializes high-level semantics.

## The analogy that anchors the primitive

**HNSW-Merger (SIGMOD 2026)** merges *proximity structures* (our Z layer) via
forward-search + lazy backward connect. We merge the **whole compound index** —
L, H, A, Z, P jointly and consistently — and our cost unit is **LLM tokens**,
not distance computations. The inversion at the core: *summaries built for
query-time retrieval are repurposed as a merge-time search structure.*

## Why merge (and not the alternatives)

- **Full rebuild** pays the entire LLM extraction+summarization bill again and
  needs the raw corpora.
- **`graphrag update` / LightRAG insert** are single-index *appends* of raw
  text: exact-title merges, union communities, no conflict handling — and they
  too need raw documents.
- **Query-time federation (SCOUT-RAG)** never materializes a merged artifact and
  pays routing cost *per query*; we pay once at merge time and amortize.
- **Privacy/federation**: two organizations can exchange indexes when they
  cannot exchange corpora — index-level merge is then the *only* option.

## Pipeline (one breath)

Normalize via adapter contract → **hybrid routing** (annotation-guided top-down
descent + cheap blocking safety net, so hybrid candidates ⊇ flat-ANN candidates
by construction) → budgeted **ER windows** (B_e entities / B_token tokens, with
a per-window recall certificate) → in-window **LLM set-clustering** emitting
*evidence only* — labeled pairs {certain, possible, cannot-link, conflict} —
→ robust **pruning** (top-M per entity, never dropping the last witness of an
ambiguity/conflict) → **global consolidation** (union-find under cannot-link
constraints; violations downgrade to ambiguity, never force-merge; cross-window
chains and implied target–target merges get explicit verification) →
out-of-place **conflict-tolerant graph merge** → affected-region detection →
community maintenance as an explicit **quality-cost knob** (attach-only / local
recluster / full recluster) → bottom-up **tree-DP annotation repair** under the
residual budget.

## The unified budget (resolves the v1↔v2 tension)

v1's selling point was "structural merge is LLM-free." v2 spends LLM tokens at
merge time (ER windows). Resolution — and the paper's strongest unifying claim:

```
minimize  tok(MERGE) = tok_ER + tok_verify + tok_repair
subject to hard invariants I1–I5 (evidence, integrity, provenance,
           conflict preservation, bounded staleness) + recall floor ρ
```

One controller allocates the budget; **routing minimizes tok_ER**, **tree-DP
minimizes tok_repair**, both priced by the same token cost model. Community
partition quality is explicitly a *soft* knob reported on a Pareto curve.

## Where v1 lives now (nothing wasted)

- **Conflict preservation + certain/possible querying** = the
  *guarantee-preserving execution layer*: over-segmentation is the **safe
  one-sided error** — a missed merge loses certain answers but never fabricates
  them; a wrong merge corrupts them. This is why "downgrade to ambiguity, never
  force-merge" is principled, not timid (consolidation soundness, Theorem 1).
- **Tree-DP repair** = maintenance under residual budget (Lemma 4 optimality;
  measured ~49% of greedy cost on hierarchical synthetic data).
- **Token cost model, affected-region completeness, GraphRAG adapter, synthetic
  benchmark** — all carried forward.

## Contributions (three, clean)

1. **Problem formulation.** Compound semantic index merging `MERGE(I_s, I_t; Θ)`
   with the unified token-budget objective and hard invariants — validated on
   three systems via a published adapter contract.
2. **Hierarchy-guided bridge search.** Budgeted, level-agnostic, *hybrid*
   routing over H×A with adaptive beam, a principled stopping rule (per-window
   recall certificate), a certified recall floor, and a cost bound
   (tok_ER ≤ n_s·L·B_token + fallback + reverify).
3. **Robust conflict-tolerant consolidation.** Evidence-only windows → global,
   order-invariant (confluent) consolidation under cannot-link constraints with
   soundness (one-sided error) — correlation-clustering hardness acknowledged,
   soundness claimed instead of approximation.

Leiden quality and summary repair are **not** contributions: maintenance
policies and evaluation axes.

## What the reviewers will say, and the prepared answers

| Attack | Answer |
|---|---|
| "Routing is the obvious thing to do with summaries" | It's formalized as constrained tree search with budgets, stopping rule, recall certificate, and cost bound — plus measured **routing regret** vs an oracle router. Mechanism is proven by the routing-recall *curve*, not asserted. |
| "ANN blocking is also sublinear — candidate counts prove nothing" | Correct; the comparison axis is **tokens / LLM-calls per recovered bridge at matched recall**. Routing's real win: it bounds LLM context per decision and reuses already-paid-for A (zero extra index build). |
| "In-window clustering = LLM-CER applied locally" | LLM-CER is our *subroutine*, cited as such. The contribution is what LLM-CER never faces: consolidating **conflicting partial clusterings across overlapping windows** under cannot-link constraints, with soundness + confluence. |
| "(L,H,A,Z,P) is cosmetic" | It's load-bearing: operators are typed against it; LightRAG's depth-1 H *predicts* a measurable cost delta (graceful degradation) — the formalism makes a falsifiable cross-system prediction. |
| "1 real system + 2 shallow adapters" | Adapter contract + LOC published; every contribution validated on ≥2 systems; skipped cells justified structurally, never by convenience. |
| "Why not federate at query time?" | SCOUT-RAG comparison: per-query routing cost vs one-time merge, amortization break-even analysis. |

## Verified novelty gap (June 2026)

No existing work merges two independently built GraphRAG-style indexes.
HNSW-Merger merges Z only; PARIS/LLM-ER merge L only; consensus clustering
merges H over a *shared* universe; GraphRAG/LightRAG updates append raw text to
one index; SCOUT-RAG federates without producing an artifact. Details and
citations: [`related_work.md`](related_work.md).

## Paper-name candidates

**BriGeRAG** (Bridge-guided GraphRAG index merging) / **SIM** (Semantic Index
Merging) / keep repo name GraphRAG-Merger for the artifact.

## Companion docs

- [`problem_definition.md`](problem_definition.md) — formal statement + theorems
- [`algorithm.md`](algorithm.md) — refined 9-step spec + pseudocode + module map
- [`evaluation.md`](evaluation.md) — datasets, baselines, metrics, budget, headline figures
- [`related_work.md`](related_work.md) — verified prior art + positioning
