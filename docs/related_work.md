# Related Work & Positioning (verified June 2026)

> Every claim below was verified against public sources (links inline).
> The novelty gap is real as of June 2026; the kill-risks are listed honestly.

## The novelty-gap statement

Prior work merges exactly **one layer** of an index: HNSW-Merger merges
proximity structure (Z), PARIS/LLM-ER merge entity sets (L), consensus
clustering merges partitions (H) over a *shared* universe; GraphRAG/LightRAG
updates append raw text to a single index; SCOUT-RAG federates at query time
without ever producing a merged artifact. **No existing system merges a
compound semantic index — low-level units, hierarchical organization,
materialized annotations, retrieval structures, and provenance, jointly and
consistently — and none exploits the already-paid-for high-level annotations
(A) as a navigable merge-time routing index for low-level bridge
construction.** That inversion — summaries built for query-time retrieval
repurposed as a merge-time search structure — is the core mechanism; the
token-denominated cost model (vs distance computations in vector-index merging)
makes it a distinct data-management primitive rather than ER glue.

## (a) GraphRAG index merging / federation

- **SCOUT-RAG** ([arXiv 2602.08400](https://arxiv.org/abs/2602.08400), Feb 2026)
  — agentic Graph-RAG over *distributed* domain graphs; federates at **query
  time** without global graph visibility. Never materializes a merged index;
  pays routing cost per query. **Closest conceptual competitor** — position as
  merge-time amortization vs per-query federation; include a break-even analysis.
- WhyHow-style multi-graph RAG — many small graphs queried independently; no
  cross-index bridging, no merged artifact.
- **No paper found** that merges two independently built GraphRAG/KG-RAG indexes.

## (b) Single-index incremental update (verified against source)

- **`graphrag update`** ([CLI docs](https://microsoft.github.io/graphrag/cli/),
  [issue #741](https://github.com/microsoft/graphrag/issues/741); source
  read in `graphrag/index/update/`): single-index append of new documents —
  entities merged by **exact title** (`groupby("title")`, `type: "first"`),
  relationships grouped by (source, target) with averaged weights, communities
  **concatenated** with id offsets (no re-clustering anywhere in the update
  path), old community reports **kept verbatim** (no refresh). No second
  pre-built index, no ambiguity/conflict handling, no report-guided matching.
- **LightRAG incremental insert** — union of node/edge sets, name-keyed dedup;
  same-corpus append that force-merges by name.

## (c) Vector-index merging (the analogy anchors)

- **HNSW-Merger** ([PACMMOD/SIGMOD 2026, DOI 10.1145/3786645](https://dl.acm.org/doi/10.1145/3786645))
  — *primary anchor*: frames vector-index merging as "a key operation in vector
  databases"; two-stage forward-search + lazy backward connect. Merges only
  proximity structure (our Z layer). **Cuts both ways**: validates the
  primitive framing, but invites "HNSW-Merger plus ER" — the (L,H,A,Z,P)
  formalization and unified token objective must carry the difference.
- [Three Algorithms for Merging HNSW Graphs (arXiv 2505.16064)](https://arxiv.org/abs/2505.16064);
  [FreshDiskANN (arXiv 2105.09613)](https://arxiv.org/pdf/2105.09613);
  SPFresh (SOSP'23) — merge/maintenance as first-class index operations.

## (d) KG/ontology merging & LLM-ER

- **PARIS / PRASE** ([arXiv 2106.08801](https://arxiv.org/pdf/2106.08801)) —
  probabilistic instance+relation+class alignment between two KGs; aligns raw
  triples (L only); no hierarchy/summary guidance, no annotations to repair,
  forced 0/1 merge decisions.
- [KG merging + partitioning for large-scale entity alignment (arXiv 2208.11125)](https://arxiv.org/pdf/2208.11125)
  — partitioning serves embedding-training scalability, not annotation-guided
  routing; outputs alignment, not a merged compound index.
- **LLM-CER** ([PACMMOD/SIGMOD 2026, DOI 10.1145/3749170](https://dl.acm.org/doi/10.1145/3749170))
  — in-context set-clustering ER. **Our in-window subroutine, not a
  competitor**: flat single-table ER; no hierarchical routing, no cross-index
  provenance; collapses rather than preserves ambiguity. Our contribution is
  what LLM-CER never faces: consolidating conflicting partial clusterings
  across overlapping windows under cannot-link constraints.
- **BEACON** ([arXiv 2603.11391](https://arxiv.org/pdf/2603.11391), SIGMOD 2026)
  + **BoostER** (WWW'24) — budget-constrained LLM-ER exists; **do not claim
  "first budget-aware LLM merge."** Differentiator: their budget covers
  matching only; ours is one end-to-end *index-level* budget spanning ER-window
  calls **and** annotation repair, jointly allocated.
- **GLEAM** (Generalized Entity Matching with Adaptivity via LLMs) — appeared
  in the SIGMOD 2026 accepted-papers listing in an earlier search, but the
  paper itself could not be located in a follow-up sweep. **Verify against the
  official accepted-papers page before citing.**

## (e) Consensus / hierarchical clustering merge

Consensus matrices, Bayesian hierarchical clustering, dendrogram combination —
all merge clusterings of the **same element set**. We merge hierarchies over
*different, partially overlapping* element sets carrying LLM-generated
annotations: structurally a different problem.

## (f) Target systems for instantiation (verified structures)

| System | H | A | Verdict |
|---|---|---|---|
| [MS GraphRAG](https://github.com/microsoft/graphrag) | multi-level Leiden hierarchy | community reports | **main system** |
| [LightRAG](https://github.com/HKUDS/LightRAG) (36k★, EMNLP'25) | depth-1 dual keyword space | entity/relation descriptions | **adapter 1** — stress-tests level-agnostic degradation |
| [Youtu-GraphRAG](https://github.com/TencentCloudADP/youtu-graphrag) (1.2k★, ICLR'26) | four-level knowledge tree | community summaries | **adapter 2** — structurally isomorphic H/A, different algorithm |
| [LeanRAG](https://github.com/KnowledgeXLab/LeanRAG) (AAAI-26, ~150★) | semantic-aggregation tree | cluster summaries | backup adapter (repo immature) |
| [HippoRAG 1/2](https://github.com/OSU-NLP-Group/HippoRAG) | **∅** (flat graph, query-time PPR) | **∅** | degenerate (L,Z,P) instance — honesty case |
| [LinearRAG](https://github.com/DEEP-PolyU/LinearRAG) (ICLR'26) | tri-partite structural only | **∅** (zero-LLM build) | degenerate case |
| [fast-graphrag](https://github.com/circlemind-ai/fast-graphrag) | ∅ | ∅ | degenerate case |

## Kill-risks (tracked openly)

1. **SCOUT-RAG** = "why not federate at query time?" → head-to-head or
   amortization analysis required in the paper.
2. **BEACON** erodes "first budget-aware" phrasing → claim end-to-end
   *index-level* budget instead.
3. **HNSW-Merger's existence** invites "HNSW-Merger + ER" → the (L,H,A,Z,P)
   formalization and the cross-system degradation prediction must carry weight.
4. **GLEAM citation currently unverifiable** → re-check before citing.
