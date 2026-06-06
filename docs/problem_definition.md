# Problem Definition

## Semantic index

A **semantic index** is a tuple

```
I = (T, E, R, C, S, P)
```

where

- `T` — set of **text units** (source chunks),
- `E` — set of **entities**, each with a name, optional type, aliases,
  description (optionally embedded), supporting `text_unit_ids`, optional
  temporal validity, and provenance,
- `R` — set of **relationships** (directed edges/claims) between entities, each
  with a relation type, description, weight, supporting `text_unit_ids`, optional
  timestamp, and provenance,
- `C` — set of **communities** (clusters of entities, possibly hierarchical),
- `S` — set of **summaries**, one materialized natural-language summary per
  community (with a coverage measure and a hash of the content it was generated
  from),
- `P` — **provenance** metadata threaded through `E`, `R`, `S`.

The dataclasses in [`../semantic_merge/schema.py`](../semantic_merge/schema.py)
are the executable form of this definition.

## The merge operation

Given two semantic indexes `I_A` and `I_B` and a configuration `θ`, produce a
single semantic index

```
I_M = merge(I_A, I_B; θ)
```

that is **consistent** (communities/summaries agree with the merged graph) and
**faithful** (no evidence is lost).

## Correctness invariants

A correct merge must satisfy:

1. **No silent evidence loss.** Every `text_unit_id` and provenance record
   present in `I_A` or `I_B` is reachable in `I_M` (possibly under a remapped,
   fused entity/edge). Nothing is dropped without being recorded.

2. **Conflict preservation.** If `I_A` and `I_B` carry contradictory claims
   about the same (canonical) entity pair and relation type, `I_M` retains both,
   linked by a **conflict set** — it must not pick one and silently discard the
   other.

3. **Referential integrity.** Every relationship endpoint in `I_M` refers to an
   entity that exists in `I_M`; every summary refers to a community that exists.

4. **Temporal monotonicity.** When two records describe the same fact at
   different times, `I_M` represents them as an ordered version chain; it does
   not collapse them into a single timeless claim.

## Quality objective (entities)

Let `≡` denote true co-reference (ground truth: two entity records denote the
same real-world entity). A good merge maximizes fusion **precision** and
**recall** w.r.t. `≡`:

- fuse `e_a, e_b` when `e_a ≡ e_b` (recall: avoid duplicates),
- keep `e_a, e_b` separate when `e_a ≢ e_b` even if names collide (precision:
  avoid bad merges — the "same name, different entity" case).

## Cost objective

Let `B` be the number of entity-pair comparisons performed during bridge
discovery, and let `ρ` be the repair cost (summed cost of the chosen repair
actions, dominated by simulated summary regenerations). The objective is to
minimize a weighted combination of `B` and `ρ` (and wall-clock time) **subject
to** the correctness invariants and a target index-quality level.

The thesis: a localized merge achieves index quality comparable to a full
rebuild at a fraction of `B + ρ`, because `ρ` scales with the size of the
**affected region**, not the whole index.

## Multi-index merge

Given `k` indexes `{I_1, …, I_k}`, repeatedly apply binary merge until one index
remains. The **order** matters for total cost (different pairings disturb
different amounts of structure). The planning problem: choose a sequence of
binary merges minimizing estimated total cost, where each candidate pair `(I_i,
I_j)` has an estimated cost `Ĉ(I_i, I_j)` and benefit (overlap / duplicate
reduction). See [`theory.md`](theory.md) §9 and [`codex_tasks.md`](codex_tasks.md)
task 3.
