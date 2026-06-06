"""Tests for the GraphRAG parquet adapter.

A tiny GraphRAG-*native*-style fixture is generated in-process (no downloads) to
verify column mapping, plus a save/load round-trip. Skipped if pyarrow is
absent (it is an optional ``[graphrag]`` extra).
"""

import pytest

pytest.importorskip("pyarrow")
import pandas as pd  # noqa: E402

from experiments.make_synthetic_indexes import build_synthetic_pair  # noqa: E402
from semantic_merge import merge_two_indexes  # noqa: E402
from semantic_merge.adapters.graphrag import load_graphrag, save_graphrag  # noqa: E402
from semantic_merge.schema import MergeConfig  # noqa: E402


def _write_native_fixture(path):
    """Write parquet files mimicking real GraphRAG output columns."""
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"id": "u1", "human_readable_id": 1, "title": "Alice Smith", "type": "person",
         "description": "an engineer", "text_unit_ids": ["t1"]},
        {"id": "u2", "human_readable_id": 2, "title": "Acme Corporation", "type": "org",
         "description": "a company", "text_unit_ids": ["t1"]},
    ]).to_parquet(path / "entities.parquet", index=False)

    # GraphRAG relationships reference entities by TITLE, not id.
    pd.DataFrame([
        {"id": "r1", "source": "Alice Smith", "target": "Acme Corporation",
         "description": "works at", "weight": 2.0, "text_unit_ids": ["t1"]},
    ]).to_parquet(path / "relationships.parquet", index=False)

    pd.DataFrame([
        {"id": "cu1", "community": 0, "level": 0, "title": "Org cluster",
         "entity_ids": ["u1", "u2"], "relationship_ids": ["r1"], "parent": -1},
    ]).to_parquet(path / "communities.parquet", index=False)

    pd.DataFrame([
        {"id": "rep1", "community": 0, "level": 0, "title": "Org cluster",
         "summary": "Alice works at Acme."},
    ]).to_parquet(path / "community_reports.parquet", index=False)

    pd.DataFrame([
        {"id": "t1", "text": "Alice Smith works at Acme Corporation.", "n_tokens": 7,
         "document_ids": ["d1"]},
    ]).to_parquet(path / "text_units.parquet", index=False)


def test_load_native_fixture(tmp_path):
    out = tmp_path / "graphrag_out"
    _write_native_fixture(out)
    idx = load_graphrag(str(out))

    assert idx.n_entities == 2
    assert idx.entities["u1"].name == "Alice Smith"      # name mapped from `title`
    assert idx.entities["u1"].type == "person"

    rel = idx.relationships["r1"]
    assert (rel.source, rel.target) == ("u1", "u2")       # titles resolved to ids
    assert rel.weight == 2.0

    assert idx.communities["0"].entity_ids == ["u1", "u2"]
    summ = next(iter(idx.summaries.values()))
    assert summ.community_id == "0"                        # report linked by community
    assert "Acme" in summ.text


def test_save_load_round_trip(tmp_path):
    _, large, _ = build_synthetic_pair(n_entities=40, seed=8)
    out = tmp_path / "rt"
    save_graphrag(large, str(out))
    back = load_graphrag(str(out))

    assert back.n_entities == large.n_entities
    assert back.n_relationships == large.n_relationships
    assert len(back.communities) == len(large.communities)
    assert len(back.summaries) == len(large.summaries)
    assert len(back.text_units) == len(large.text_units)
    # endpoints still valid after round-trip
    for r in back.relationships.values():
        assert r.source in back.entities and r.target in back.entities


def test_load_merge_save_workflow(tmp_path):
    """The intended real workflow: two GraphRAG dirs -> merge -> GraphRAG dir."""
    small, large, _ = build_synthetic_pair(n_entities=40, overlap=0.4, seed=9)
    save_graphrag(small, str(tmp_path / "a"))
    save_graphrag(large, str(tmp_path / "b"))

    a = load_graphrag(str(tmp_path / "a"))
    b = load_graphrag(str(tmp_path / "b"))
    merged = merge_two_indexes(a, b, MergeConfig(namespace_ids=False))
    assert merged.n_entities < a.n_entities + b.n_entities  # dedup happened

    save_graphrag(merged, str(tmp_path / "merged"))
    reloaded = load_graphrag(str(tmp_path / "merged"))
    assert reloaded.n_entities == merged.n_entities
