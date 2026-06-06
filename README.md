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

> **Status: scaffold.** The data model ([`semantic_merge/schema.py`](semantic_merge/schema.py))
> is implemented and importable. The algorithmic modules expose their final
> signatures with full docstrings and raise `NotImplementedError` — they are
> filled in by **Task 1**. See [Status](#status).

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
├── semantic_merge/             # the package
│   ├── schema.py               # ✅ data model (implemented)
│   ├── loader.py               # JSON (de)serialization
│   ├── bridge.py               # semantic bridge discovery
│   ├── prune.py                # robust pruning (preserves ambiguity/conflict)
│   ├── entity_merge.py         # conflict-aware entity fusion
│   ├── edge_reconcile.py       # relationship reconciliation
│   ├── affected_region.py      # affected-community detection
│   ├── repair_planner.py       # cheapest-repair-under-threshold planner
│   └── merge.py                # binary merge orchestration
├── experiments/                # synthetic benchmark harness
│   ├── make_synthetic_indexes.py
│   ├── run_merge.py
│   ├── eval_index_quality.py
│   └── eval_cost.py
└── tests/                      # unit tests (pytest)
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python ≥ 3.10. Core dependencies are minimal (`numpy` for embedding
similarity); `pytest` for the test suite.

## Quickstart

The data model is usable today:

```python
from semantic_merge import SemanticIndex, Entity, MergeConfig

idx = SemanticIndex(name="demo")
idx.add_entity(Entity(id="e1", name="Ada Lovelace", type="person",
                      aliases=["Ada", "A. Lovelace"]))
print(idx.n_entities)  # 1
```

`merge_two_indexes(a, b, MergeConfig())` is wired end-to-end but its leaf steps
land in Task 1.

## Run the tests

```bash
pytest
```

Test stubs currently `skip` with the assertions they should make; Task 1
replaces the skips with real tests.

## Run the experiments

Implemented in Task 2 (synthetic benchmark). Once landed:

```bash
python -m experiments.run_merge        # compare naive / name-only / semantic merge
```

See [`docs/experiments.md`](docs/experiments.md) for the metrics and the
comparisons we expect to demonstrate.

## How this repo gets built (for the agent)

This repo is designed to be implemented by the **Codex cloud agent**, which runs
sandboxed with **no network access** — so every bit of context it needs is
already committed here (docs + schema + this README). Work proceeds as four
ordered GitHub issues; paste each prompt from [`docs/codex_tasks.md`](docs/codex_tasks.md):

1. **Implement MVP semantic index merge prototype** — fill in the algorithmic modules + tests.
2. **Add synthetic conflict-heavy benchmark and metrics** — the offline experiment harness.
3. **Implement multi-index semantic merge planner** — `merge_k_indexes` + merge-order strategies.
4. **Add GraphRAG parquet adapter** — load/save real GraphRAG outputs.

## Status

| Component | State |
|---|---|
| `schema.py` (data model) | ✅ implemented |
| Pipeline orchestration (`merge.py` data-flow) | ✅ wired (leaves pending) |
| Algorithmic modules (bridge/prune/fuse/reconcile/region/repair) | ⬜ Task 1 |
| Unit tests | ⬜ Task 1 (stubs in place) |
| Synthetic benchmark + metrics | ⬜ Task 2 |
| Multi-index planner | ⬜ Task 3 |
| GraphRAG parquet adapter | ⬜ Task 4 |

## License

MIT.
