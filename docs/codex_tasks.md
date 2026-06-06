# Codex Tasks

> **Status:** Tasks 1–3 are **implemented and tested** (21 passing tests, working
> binary + multi-index merge, synthetic benchmark). **Task 4 (GraphRAG parquet
> adapter) is the active next task.** The prompts for 1–3 are kept below as a
> record of scope and as regression specs. Filling in the formal proofs in
> [`theory.md`](theory.md) is separate follow-up work.

Staged build plan for the Codex cloud agent. Each task is a self-contained
GitHub issue: copy the **Prompt** block into the issue body. Do the tasks **in
order** — later tasks assume earlier ones landed.

> **Why staged.** The Codex cloud agent runs in an isolated container with **no
> external network access** during execution. Everything it needs must already
> be in the repo (these docs, the schema, the synthetic data generator). Don't
> ask it to fetch papers or hit APIs.

Global constraints (repeat in every issue):

- Keep the implementation **simple and readable**.
- **No external LLM API calls**; no network. Summary "regeneration" is modeled by
  cost/coverage proxies, not real generation.
- **Pure Python + common packages only** (stdlib; `numpy` allowed for embeddings;
  `pytest` for tests).
- Include **docstrings and type hints**; keep `from __future__ import annotations`.
- The data model in `semantic_merge/schema.py` is the contract — extend it if
  needed, don't fork it.
- Keep `pytest` green; replace `pytest.skip(...)` stubs with real assertions.

---

## Task 1 — Implement MVP semantic index merge prototype  ✅ done

**Issue title:** `Implement MVP semantic index merge prototype`

**Prompt:**

```
Implement the MVP for the semantic_merge package. The data model
(semantic_merge/schema.py) is complete; fill in the algorithmic modules, which
currently raise NotImplementedError. Read docs/idea.md and
docs/problem_definition.md first — the four correctness invariants there are
mandatory.

Implement, with docstrings, type hints, and unit tests:

1. loader.py — JSON load/save for SemanticIndex that round-trips the schema.

2. bridge.py — discover_entity_bridges(index_small, index_large, config):
   multi-signal scoring (normalized name, alias overlap, type compatibility,
   description-embedding cosine when embeddings exist, neighbor overlap,
   temporal compatibility). Apply a blocking key so you do NOT compare all
   N_small * N_large pairs. Record per-signal scores in BridgeCandidate.features.

3. prune.py — robust_semantic_prune(...): keep at most M candidates per source
   entity, drop hard type/time-incompatible ones, and PRESERVE ambiguous and
   conflict candidates (return retained / ambiguities / conflicts).

4. entity_merge.py — merge_entities(...): high-confidence bridges fuse;
   low-confidence stay separate; ambiguous become preserved records. Fusion is
   loss-less (union aliases, text_unit_ids, provenance; reconcile timestamps).
   Return (merged_entities, id_map, conflicts).

5. edge_reconcile.py — reconcile_edges(...): remap endpoints via id_map, group
   by (source, target, relation_type), merge compatible edges, version temporal
   updates, and preserve contradictions as ConflictSets. Never overwrite
   evidence.

6. affected_region.py — detect_affected_communities(...): return a COMPLETE
   (no false negatives) set of communities disturbed by the merge.

7. repair_planner.py — compute_drift(...) and plan_local_repairs(...): drift =
   alpha*entity_change_ratio + beta*edge_change_ratio + gamma*boundary_change +
   delta*conflict_density + epsilon*summary_coverage_drop. Choose the cheapest
   action (NOOP < PATCH_SUMMARY < REGENERATE_SUMMARY < LOCAL_RECLUSTER <
   FULL_REGION_REBUILD) with drift <= threshold and coverage >= threshold.

8. merge.py — finish merge_two_indexes(...): the pipeline skeleton/data-flow is
   already written; implement the lazy reverse consolidation step and the final
   assembly + repair-plan application so the function returns a valid
   SemanticIndex.

9. tests/ — replace the pytest.skip stubs in tests/test_*.py with real
   assertions covering the bullet points listed in each test file's docstring.

Constraints: simple/readable, no LLM/network calls, pure Python + numpy,
docstrings + type hints. Update the README "Status" section to mark task 1 done.
```

---

## Task 2 — Add synthetic conflict-heavy benchmark and metrics  ✅ done

**Issue title:** `Add synthetic conflict-heavy benchmark and metrics`

**Prompt:**

```
Implement the experiment harness in experiments/. Read docs/experiments.md.

1. make_synthetic_indexes.py — build_synthetic_pair(n_entities, overlap,
   conflict_rate, seed) returning (I_A, I_B, GroundTruth). Plant: duplicated
   entities, alias variations, same-name-different-entity pairs, relationship
   conflicts, temporal updates, and stale summaries. All randomness via
   random.Random(seed) — deterministic, offline.

2. run_merge.py — implement naive_union_merge and name_only_merge baselines, and
   a main() that builds a synthetic pair and runs all three strategies (naive,
   name-only, semantic) printing a comparison table.

3. eval_index_quality.py — evaluate_quality(merged, truth): entity duplicate
   rate, edge conflict preservation rate, #affected communities, #repaired
   summaries.

4. eval_cost.py — time_merge(...): wall-clock seconds (time.perf_counter),
   bridge comparison count, repair cost.

Show in the printed table that semantic merge gets LOW duplicate rate AND HIGH
conflict preservation simultaneously, which neither baseline achieves. Add a
README section showing how to run the experiments. Keep everything deterministic
and offline.
```

---

## Task 3 — Implement multi-index semantic merge planner  ✅ done

**Issue title:** `Implement multi-index semantic merge planner`

**Prompt:**

```
Extend the prototype with multi-index merge planning. Read docs/theory.md §9.

Implement merge_k_indexes(indexes, config, strategy) supporting strategies:
random, small_first, large_first, semantic_aware.

semantic_aware uses the cost estimator:
  C_hat(Ii, Ij) = c_alpha * N_small * log(N_large)
                + c_beta  * candidate_pairs
                + c_gamma * conflict_risk
                + c_delta * affected_communities
                + c_epsilon * summary_repair_cost
and benefit = overlap + duplicate_reduction, greedily merging the pair that
minimizes C_hat / (1 + benefit) until one index remains.

Add experiments varying k in {2, 4, 8, 16} comparing merge time and quality
across strategies; expect semantic_aware to win, with the gap over random
widening as k grows. Add tests for the planner and a README note. Deterministic,
offline.
```

---

## Task 4 — Add GraphRAG parquet adapter  ⬅ next

**Issue title:** `Add GraphRAG parquet adapter`

**Prompt:**

```
Add an adapter that loads a real Microsoft GraphRAG output directory (parquet
files: entities, relationships, communities, community_reports, text_units) into
a SemanticIndex, and writes a merged SemanticIndex back out in the same layout.

Put it in semantic_merge/adapters/graphrag.py with load_graphrag(path) ->
SemanticIndex and save_graphrag(index, path). Map GraphRAG columns onto the
schema fields; handle missing optional columns gracefully. Add a small
fixture-based test (commit a tiny synthetic parquet set, do NOT download
anything). Keep core package import-light: import pandas/pyarrow lazily inside
the adapter only. Document usage in the README.
```

---

## Explicitly out of scope for now

Do **not** attempt these until tasks 1–3 are solid:

- wiring into a full live GraphRAG system / real large-scale corpora;
- real LLM calls for summary patching/regeneration;
- complex production-grade community reclustering;
- writing the full research paper.

Keep each PR scoped to one task.
