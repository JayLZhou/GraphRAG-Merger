# Evaluation Plan (v2)

> Feasibility-reviewed experiment design. Supersedes the synthetic-only plan in
> [`experiments.md`](experiments.md) (which remains valid for the offline
> benchmark already implemented).

## 1. Datasets, index construction, bridge ground truth

For each dataset, partition the corpus into halves A and B; build I_A and I_B
**independently** (separate runs, seeds, no shared state) per system; merge I_B
into I_A.

| Dataset | Split protocol | Bridge GT (tier) | Role |
|---|---|---|---|
| **2WikiMultiHopQA** (primary) | Supporting docs split A/B; shared-entity overlap ρ ∈ {5, 20, 50}% | Wikidata QIDs + shipped KB triples (near-exact) | Only corpus with free high-precision entity GT; queries *require* cross-index bridges |
| HotpotQA / MuSiQue | Same protocol | Hyperlink anchors (distant supervision) + 300–500 manually labeled pairs, 2 annotators, report κ | Standard multihop; manual sample covers possible/conflict labels |
| Multi-News / CC-News by outlet | Split by outlet, same events | Entity linking + manual sample; **planted conflicts** (perturbed dates/numbers/roles) | Natural duplication; conflict-label GT |
| UltraDomain (1–2 domains) | Split by document | Planted duplicates via alias/rename perturbation (exact) | LightRAG-paper comparability; adapter runs |

Three GT tiers — planted (exact), distant supervision (high precision), manual
sample (label quality) — assigned per-RQ.

## 2. Baselines

| ID | Baseline | Description | Serves |
|---|---|---|---|
| B0 | **Full Rebuild ×3 seeds** (oracle) | Reindex A∪B from scratch; fidelity target + cost ceiling + **noise band** | RQ1, RQ5, RQ6 |
| B1 | Naive Union | Disjoint graph union, no ER | RQ1 |
| B2 | Name-Type merge | Force-merge on exact (name, type) | RQ1, RQ3 |
| B3 | Embedding-only merge | Cosine-threshold force-merge | RQ3 |
| B4 | Flat Blocking + LLM-ER | ANN/ngram blocking → windowed LLM-ER, **no routing** | RQ1, RQ2, RQ3 |
| B5 | Global LLM-ER (subsampled) | Blocked pairs on 5–10% entity sample, recall extrapolated with CIs | RQ3 upper bound |
| B6 | GraphRAG-incremental-style | Half-B raw docs through native `graphrag update` on I_A | RQ1 |
| B7 | **Ours** | Routed windows + hybrid fallback + consolidation + repair, at several unified budgets T | all |

## 3. Metric definitions

**Merge cost:** LLM tokens (in/out, priced), LLM calls, wall-clock.

**Query-behavior similarity to rebuild (RQ1).** Critical methodological move:
**rebuild is nondeterministic** — run B0 with 3 seeds and report
rebuild-vs-rebuild self-agreement as the **noise band**; the claim is that the
merged index falls *within* it. On a fixed query set Q (cross-half multihop +
global sensemaking): (a) answer agreement EM/F1 vs rebuild; (b) **absolute QA
EM/F1 vs gold** (primary if self-agreement is low); (c) retrieval Jaccard@k
over chunks/entities/communities; (d) LLM-judge pairwise win-rate (fixed
judge+seed, both orders); (e) global-search coverage: fraction of gold
cross-half entity pairs co-resident in some community; (f) **conflict-awareness
P/R** of certain/possible answers vs planted conflicts (unique to us).

**Routing recall:** RR@cost = |gold bridge pairs co-resident in some examined
window| / |gold pairs|, vs cumulative ER tokens (tokens-per-recovered-bridge at
matched recall — *not* candidate counts; ANN blocking is also sublinear).

**Bridge quality:** per-label P/R/F1 over {certain, possible, cannot-link, conflict}.

**Preservation under pruning:** fraction of GT ambiguity/conflict pairs
surviving M-bounded pruning; certain-answer invariance violation rate.

**Maintenance/repair:** NMI + modularity vs rebuild communities; repair tokens
vs staleness (LLM-judged report coverage vs rebuild reports).

## 4. RQ × system matrix

Main = MS GraphRAG (full). Adapters = **LightRAG** (depth-1 H) and
**Youtu-GraphRAG** (multi-level tree). Skipped cells justified structurally,
never by convenience. Adapter contract (exact L,H,A,Z,P mapping + adapter LOC)
published per system.

| RQ | Baselines | GraphRAG | LightRAG | Youtu | Datasets |
|---|---|---|---|---|---|
| RQ1 cost vs rebuild fidelity | B0,B1,B2,B4,B6 | full | yes | yes | all (adapters: 2Wiki+UltraDomain) |
| RQ2 routing vs flat blocking | B4 ± hybrid | full | **inapplicable** (no hierarchy → graceful-degradation evidence) | yes | 2Wiki, news |
| RQ3 bridge quality | B2,B3,B4,B5 | full | yes | — | 2Wiki, UltraDomain |
| RQ4 pruning M ∈ {1,2,4,8,∞} | self | full | — | — | 2Wiki |
| RQ5 policies A/B/C | B0 communities | full | inapplicable | spot-check | 2Wiki, news |
| RQ6 repair | regen-all, greedy, tree-DP | full | inapplicable | — | 2Wiki |

Each contribution validated on ≥2 systems; the full matrix runs once
(~1.3× cost, not 3×).

## 5. Ablations

(1) −routing (B4); (2) −hybrid fallback (routing-only recall loss);
(3) eager vs lazy consolidation (order-dependence divergence);
(4) −cannot-link constraints; (5) −implied target–target verification and
−chain verification (wrong-merge rate); (6) window budget (B_e, B_token) sweep;
(7) beam fixed vs adaptive; (8) unified budget T and its ER/repair split;
(9) cheap vs strong ER model.

## 6. LLM budget strategy

~10M-token union corpus → 30–60M tokens/rebuild (mini-class model: $10–40);
×3 seeds ×4 datasets ×3 systems ≈ $500–1.5k for rebuild baselines; merge-side
runs cheaper by construction; subsampled global oracle ≈ $10–50.
**Total: low thousands of dollars — state it in the paper.**
Cost controls: cheap model for extraction/ER, strong model only for judging;
hash-keyed call cache reused across ablations (windows are deterministic given
inputs); full ablation matrix on 2 datasets; **record/replay cache shipped as
artifact** + deterministic string-similarity surrogate mode for zero-cost
reproduction and CI.

## 7. Headline figures

1. **Cost–fidelity Pareto frontier:** merge-time LLM tokens (log x) vs query
   fidelity (y), rebuild self-agreement band shaded; points = B1, B2, B4, Ours
   at several unified budgets, B0. Renders the unified-budget claim visually.
2. **Routing-recall curve:** bridge recall vs cumulative ER tokens —
   report-guided descent vs flat blocking vs hybrid. Proves H/A-guidance is the
   mechanism, not just the pipeline.

## 8. Scalability

Wikipedia-category corpora scaling 10k → 500k entities per half (surrogate mode
at the largest scales to isolate routing/consolidation scaling from LLM spend).
Measure: merge tokens and wall-clock vs |I_B| and ρ; empirical check of
tok_ER ≤ n_s·L·B_token; consolidation time vs (m+c); **sequential-merge chain**
(k = 4–8 successive merges) testing drift, idempotence, ambiguity-set growth.
Routing comparisons O(n_s·L·b·log N_t) empirically vs flat O(n_s·N_t).

## 9. Risks & mitigations

- **Rebuild self-agreement may be low** (community formation is unstable) →
  lead with absolute QA accuracy + conflict-awareness; agreement secondary.
- **Planted conflicts may look synthetic** → anchor with the manually labeled
  natural-news sample.
- **Youtu-GraphRAG provenance under-documented** → verify chunk traceability
  before committing; LeanRAG held as backup adapter.
