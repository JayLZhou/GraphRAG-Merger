# Idea: Efficient Semantic Index Merging for Graph-Augmented RAG

## One-line

Merging two graph-augmented RAG indexes should be a **first-class, correctness-preserving, sub-rebuild-cost operation** — not a naive union and not a full re-build.

## Motivation

Graph-augmented RAG systems (e.g. Microsoft GraphRAG) don't retrieve over raw
chunks alone. They build a **semantic index**: entities and relationships are
extracted from text, clustered into communities, and each community gets a
materialized natural-language **summary**. Query-time retrieval and global
"sense-making" run over this structured artifact.

Building a semantic index is expensive — it is dominated by LLM calls for
entity/relationship extraction and for community summarization. So once you have
indexes, you very often need to **combine** them:

- **Incremental ingestion** — a new batch of documents arrives; you've already
  indexed it separately and want to fold it into the main index.
- **Federation** — different teams/sources each maintain an index; you want a
  unified view.
- **Sharded builds** — a large corpus was indexed in parallel shards that must
  be reconciled.

Today there are two bad options:

1. **Naive union.** Concatenate everything. This *duplicates* entities ("John
   Smith" appears twice), produces dangling/duplicated edges, and — worst —
   **silently drops or overwrites conflicting evidence**. Community structure
   and summaries become inconsistent with the merged graph.
2. **Full rebuild.** Re-extract and re-summarize from the union of all text.
   Correct, but pays the full (LLM-dominated) build cost *again*, discarding all
   prior work. It scales terribly when merges are frequent or indexes are large.

## The core insight

A merge perturbs only **part** of the graph. If we can (a) correctly identify
*which* entities co-refer across indexes, (b) reconcile edges **without losing
evidence**, and (c) **localize** the disturbance to a small set of affected
communities, then we only need to repair that small region — and we can pick the
*cheapest* repair that still yields a correct index. The expensive operations
(LLM summary regeneration, reclustering) are applied surgically, not globally.

This turns "merge" into an operation whose cost scales with **how much actually
changed**, not with total index size.

## Approach (the pipeline)

Given two indexes `A` and `B`:

1. **Orient** — search forward from the *smaller* index into the larger one.
   This is the key to the `O(N_small · log N_large)` cost bound (with blocking).
2. **Semantic bridge discovery** — for each small-index entity, find candidate
   correspondences in the large index using *multiple* signals (name, alias,
   type, description-embedding, neighbor overlap, temporal compatibility) so no
   single noisy signal dominates.
3. **Robust pruning** — bound candidates per entity, drop hard-incompatible
   ones, and **explicitly preserve ambiguity and conflict** rather than guessing.
4. **Lazy reverse consolidation** — large-index entities with no forward match
   are carried over; their reverse candidacy is recorded for on-demand
   resolution instead of a second full search.
5. **Conflict-aware entity fusion** — high-confidence bridges fuse; low-confidence
   stay separate; ambiguous pairs become preserved ambiguity records. Fusion is
   loss-less on evidence (aliases, text units, provenance, time).
6. **Edge reconciliation** — remap endpoints to canonical ids, merge compatible
   edges, **version** temporal updates, and **preserve contradictions** as
   conflict sets. Never silently overwrite evidence.
7. **Affected-region detection** — compute the (complete) set of communities the
   merge disturbed.
8. **Local repair planning** — for each affected community, choose the cheapest
   action (`NOOP < PATCH_SUMMARY < REGENERATE_SUMMARY < LOCAL_RECLUSTER <
   FULL_REGION_REBUILD`) that brings a drift score under threshold while keeping
   summary coverage acceptable.
9. **Assemble** the merged index and apply the repair plan.

For **multiple** indexes, a **semantic-aware planner** chooses the merge *order*:
each binary merge has an estimated cost and an estimated benefit (overlap /
duplicate reduction), and we greedily merge the pair minimizing `cost / (1 +
benefit)`.

## What makes it a research contribution

- **Correctness invariants** for index merging: *no silent evidence loss* and
  *conflict preservation*. These are stated precisely and tested.
- An **equivalence-to-rebuild oracle**: define when the localized merge yields an
  index equivalent to a full rebuild, and characterize the gap when it doesn't.
- A **cost model** showing binary merge is sub-quadratic via blocking + smaller-side
  forward search, and a **local repair optimality** result for independent
  communities (with a tree-DP extension for hierarchical communities).
- A **multi-index merge-order** cost model with empirical validation.

The formal statements live in [`theory.md`](theory.md); the experimental plan
(synthetic benchmarks + metrics + baselines) lives in [`experiments.md`](experiments.md);
the precise problem statement is in [`problem_definition.md`](problem_definition.md).

## Scope discipline (what the first version deliberately does NOT do)

To keep the prototype focused and self-contained:

- **No real GraphRAG parquet ingestion** in v1 (added later as an adapter).
- **No real LLM calls** — summary "regeneration" is modeled by cost/coverage
  proxies so the algorithm and benchmarks are deterministic and offline.
- **No large-scale real-world experiments** until the synthetic benchmark
  validates the algorithm and invariants.

The build order is staged in [`codex_tasks.md`](codex_tasks.md).
