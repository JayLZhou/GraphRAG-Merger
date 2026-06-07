# GraphRAG-Merger

**Efficient semantic index merging for graph-augmented RAG systems.**

Merging two graph-augmented RAG indexes (à la [Microsoft GraphRAG](https://github.com/microsoft/graphrag))
should be a **first-class, correctness-preserving, sub-rebuild-cost** operation —
not a naive `union` (which duplicates entities and silently drops conflicting
evidence) and not a full LLM-driven re-build (which throws away all prior work).

This repo is a research prototype: a clean, dependency-light Python package
(`semantic_merge`) plus an offline synthetic benchmark. It is built **module by
module by an agent** following the staged plan in
[`docs/codex_tasks.md`](docs/codex_tasks.md).

> **Status: implemented (Tasks 1–4).** The full binary-merge pipeline, the
> multi-index planner, the offline synthetic benchmark, the GraphRAG parquet
> adapter, and the test suite are implemented and green (33 tests; the core
> package has zero third-party runtime deps — the adapter's pandas/pyarrow are
> an optional extra, imported lazily). The conflict-tolerant merge, tree-DP
> repair planner, and certain/possible query layer (the SIGMOD direction) are in
> too. The formal proofs in [`docs/theory.md`](docs/theory.md) remain follow-up
> work. See [Status](#status).

## The idea in one paragraph

A merge only perturbs *part* of the graph. If we correctly identify which
entities co-refer across indexes, reconcile edges **without losing evidence**,
and **localize** the disturbance to a small set of affected communities, then we
only need to repair that small region — picking the *cheapest* repair that still
yields a correct index. Expensive operations (summary regeneration,
reclustering) are applied surgically, not globally, so merge cost scales with
*how much actually changed*, not with total index size. Full write-up:
[`docs/idea.md`](docs/idea.md).

## Pipeline

```
merge_two_indexes(A, B)
  1. orient            pick the smaller index, search forward into the larger
  2. bridge discovery  multi-signal entity correspondence (name/alias/type/embedding/neighbor/time)
  3. robust prune      bound candidates per entity; PRESERVE ambiguity & conflict
  4. lazy reverse      carry over unmatched large-index entities; defer reverse resolution
  5. entity fusion     conflict-aware: fuse high-confidence, keep evidence loss-less
  6. edge reconcile    remap endpoints, merge compatible, version time, PRESERVE contradictions
  7. affected region   complete set of disturbed communities
  8. repair planning   cheapest action under a drift/coverage threshold, per community
  9. assemble          build merged index, apply repair plan
```

Correctness invariants enforced throughout: **no silent evidence loss** and
**conflict preservation** (full list in [`docs/problem_definition.md`](docs/problem_definition.md)).

## Repository layout

```
GraphRAG-Merger/
├── README.md
├── pyproject.toml
├── docs/
│   ├── idea.md                 # motivation + approach (start here)
│   ├── problem_definition.md   # formal index def + correctness invariants
│   ├── theory.md               # theorem skeleton, each tied to a module
│   ├── experiments.md          # synthetic benchmark + metrics + baselines
│   └── codex_tasks.md          # staged build plan (paste into GitHub issues)
├── semantic_merge/             # the package (pure stdlib)
│   ├── schema.py               # data model (dataclasses, configs, result types)
│   ├── util.py                 # name normalization + similarity helpers
│   ├── loader.py               # JSON (de)serialization
│   ├── bridge.py               # semantic bridge discovery (multi-signal + blocking)
│   ├── prune.py                # robust pruning (preserves ambiguity/conflict)
│   ├── entity_merge.py         # conflict-aware entity fusion (union-find)
│   ├── edge_reconcile.py       # relationship reconciliation (+ versioning, conflicts)
│   ├── affected_region.py      # affected-community detection (multi-level)
│   ├── partition_reconcile.py  # merge two community partitions (Stage 8)
│   ├── repair_planner.py       # cost-optimal repair: min-cost feasible + tree-DP
│   ├── query.py                # certain/possible answering over conflicts
│   ├── merge.py                # binary + multi-index merge orchestration
│   └── adapters/
│       └── graphrag.py         # load/save Microsoft GraphRAG parquet (optional)
├── experiments/                # synthetic benchmark harness
│   ├── make_synthetic_indexes.py   # planted-phenomena generator + ground truth
│   ├── run_merge.py                # naive / name-only / semantic comparison
│   ├── run_multi_merge.py          # multi-index merge-order strategies
│   ├── eval_index_quality.py
│   └── eval_cost.py
└── tests/                      # unit + integration tests (pytest)
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # only dev extra (pytest); runtime deps: none
```

Requires Python ≥ 3.10. The package has **zero third-party runtime
dependencies** — pure standard library.

## Quickstart

```python
from semantic_merge import SemanticIndex, Entity, Relationship, MergeConfig, merge_two_indexes

a = SemanticIndex(name="A")
a.add_entity(Entity(id="a1", name="Ada Lovelace", type="person", aliases=["A. Lovelace"]))

b = SemanticIndex(name="B")
b.add_entity(Entity(id="b1", name="Ada Lovelace", type="person"))   # same entity, other index

merged = merge_two_indexes(a, b, MergeConfig(namespace_ids=False))
print(merged.n_entities)                       # 1  (the two were fused)
print(merged.metadata["id_map"])               # {'a1': 'a1', 'b1': 'a1'}  (canonical)
```

## Run the tests

```bash
pytest        # 21 passed
```

## Run the experiments

```bash
# Binary merge: naive union vs name-only vs semantic, on a conflict-heavy pair
python -m experiments.run_merge --n 200 --overlap 0.4 --conflict-rate 0.3

# Multi-index merge-order strategies across k = 2, 4, 8, 16
python -m experiments.run_multi_merge
```

Representative `run_merge` output (lower `dup_rate`/`wrong_merge` better, higher
`conflict_keep` better):

```
strategy       dup_rate  wrong_merge  conflict_keep  affected  repaired  compares
naive_union        1.00         0.00           0.00         0         0         0
name_only          0.60         1.00           0.00         0         0         0
semantic           0.00         0.00           1.00        25        23      5089
```

The semantic merge reaches **low duplicate rate AND low wrong-merge AND high
conflict preservation simultaneously** — the Pareto point neither baseline can,
while scoring far fewer than the `N_small · N_large` brute-force comparisons.
See [`docs/experiments.md`](docs/experiments.md) for the full metric definitions.

## Build plan & remaining work

The staged plan lives in [`docs/codex_tasks.md`](docs/codex_tasks.md) as four
ordered GitHub-issue prompts (written so the **Codex cloud agent** — sandboxed
with no network access — has all context in-repo). All four are implemented:

1. ✅ **MVP semantic index merge prototype** — algorithmic modules + tests.
2. ✅ **Synthetic conflict-heavy benchmark and metrics** — offline harness.
3. ✅ **Multi-index semantic merge planner** — `merge_k_indexes` + strategies.
4. ✅ **GraphRAG parquet adapter** — load/save real GraphRAG outputs.

The formal proofs in [`docs/theory.md`](docs/theory.md) remain a skeleton (each
theorem is stated and tied to its module); filling them in is follow-up work.

### Use the GraphRAG adapter

```python
from semantic_merge.adapters.graphrag import load_graphrag, save_graphrag
from semantic_merge import merge_two_indexes
from semantic_merge.schema import MergeConfig

a = load_graphrag("ragtest_a/output")     # a GraphRAG output directory
b = load_graphrag("ragtest_b/output")
merged = merge_two_indexes(a, b, MergeConfig())
save_graphrag(merged, "merged/output")
```

Requires the extra: `pip install -e ".[graphrag]"` (pandas + pyarrow).

### Conflict-tolerant querying (certain / possible answers)

The merge **preserves** cross-source contradictions rather than resolving them,
and you can query the result with consistent-query-answering semantics:

```python
from semantic_merge import query

# A says (Alice, Acme) status = active; B says inactive — kept, not resolved.
ans = query.query_relationship(merged, "a1", "a2", "status")
ans["exists"]    # {'certain': True,  'possible': True}    -> the edge holds in every repair
ans["claim"]     # {'certain': [], 'possible': ['active','inactive']}  -> no single claim is certain
ans["contested"] # True
```

The repair planner is a **cost-based optimizer**: it spends LLM budget only on
the affected region, choosing the min-token-cost action per community, and on a
hierarchical (Leiden) community tree it uses **tree-DP** to decide — optimally —
whether to fix children individually or rebuild a whole subtree at once.
Contested communities get **conflict-aware** summaries ("Sources disagree: …").

## Status

| Component | State |
|---|---|
| `schema.py` (data model) | ✅ implemented |
| Binary merge pipeline (`merge_two_indexes`) | ✅ implemented |
| Conflict-preserving fusion + edge reconciliation | ✅ implemented |
| Partition reconciliation (Stage 8) | ✅ implemented |
| Token-grounded cost model + min-cost-feasible planner | ✅ implemented |
| Tree-DP repair planner (hierarchical) + COMPOSE | ✅ implemented |
| Conflict-aware summaries | ✅ implemented |
| Certain / possible query layer (`query.py`) | ✅ implemented |
| Multi-index planner (`merge_k_indexes`) | ✅ implemented |
| GraphRAG parquet adapter | ✅ implemented (optional extra) |
| Unit + integration tests | ✅ 33 passing |
| NP-hardness proof + tree-DP optimality writeup (`docs/theory.md`) | ⬜ stated, not proved |
| Large-scale + downstream-QA experiments | ⬜ pending |

## License

MIT.
