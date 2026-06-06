"""Integration tests for the binary and multi-index merge entrypoints."""

from experiments.eval_index_quality import evaluate_quality
from experiments.make_synthetic_indexes import build_synthetic_k, build_synthetic_pair
from semantic_merge import merge_k_indexes, merge_two_indexes
from semantic_merge.schema import MergeConfig


def test_binary_merge_end_to_end():
    small, large, gt = build_synthetic_pair(n_entities=60, overlap=0.4, conflict_rate=0.3, seed=3)
    merged = merge_two_indexes(small, large, MergeConfig(namespace_ids=False))

    # dedup happened: fewer entities than a naive union.
    assert merged.n_entities < small.n_entities + large.n_entities
    # audit trail present.
    for key in ("id_map", "conflicts", "repair_plan", "affected_communities"):
        assert key in merged.metadata
    # referential integrity: every edge endpoint exists.
    for rel in merged.relationships.values():
        assert rel.source in merged.entities
        assert rel.target in merged.entities

    q = evaluate_quality(merged, gt)
    assert q.entity_duplicate_rate <= 0.1   # high fusion recall
    assert q.wrong_merge_rate == 0.0        # perfect precision on same-name-distinct
    assert q.edge_conflict_preservation_rate >= 0.9


def test_multi_index_merge_reduces_to_one():
    indexes, universe = build_synthetic_k(k=4, universe=40, appear_prob=0.6, seed=1)
    merged = merge_k_indexes(indexes, MergeConfig(), strategy="semantic_aware", seed=1)
    assert merged.metadata["strategy"] == "semantic_aware"
    assert "total_bridge_comparisons" in merged.metadata
    # dedup pulls the final count toward the universe size, well under the input.
    input_total = sum(i.n_entities for i in indexes)
    assert merged.n_entities <= input_total
    assert merged.n_entities <= int(universe * 1.5)


def test_all_strategies_run():
    indexes, _ = build_synthetic_k(k=4, universe=30, appear_prob=0.6, seed=2)
    for strategy in ("random", "small_first", "large_first", "semantic_aware"):
        merged = merge_k_indexes(list(indexes), MergeConfig(), strategy=strategy, seed=2)
        assert merged.n_entities > 0
