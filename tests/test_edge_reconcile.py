"""Unit tests for relationship reconciliation."""

from semantic_merge.edge_reconcile import reconcile_edges
from semantic_merge.schema import ConflictKind, MergeConfig, Relationship, SemanticIndex


def _idx(*rels: Relationship) -> SemanticIndex:
    idx = SemanticIndex()
    for r in rels:
        idx.add_relationship(r)
    return idx


def test_endpoints_remapped():
    small = _idx(Relationship(id="r", source="a1", target="a2", relation_type="knows"))
    id_map = {"a1": "X", "a2": "Y"}
    merged, _ = reconcile_edges(small, SemanticIndex(), id_map, MergeConfig())
    rel = next(iter(merged.values()))
    assert (rel.source, rel.target) == ("X", "Y")


def test_duplicate_edges_merged():
    small = _idx(Relationship(id="rs", source="a", target="b", relation_type="knows", text_unit_ids=["t1"]))
    large = _idx(Relationship(id="rl", source="c", target="d", relation_type="knows", text_unit_ids=["t2"]))
    id_map = {"a": "X", "b": "Y", "c": "X", "d": "Y"}
    merged, conflicts = reconcile_edges(small, large, id_map, MergeConfig())
    assert len(merged) == 1
    rel = next(iter(merged.values()))
    assert set(rel.text_unit_ids) == {"t1", "t2"}
    assert conflicts == []


def test_temporal_update_versioned():
    small = _idx(Relationship(id="rs", source="a", target="b", relation_type="role",
                              valid_from="2023", attributes={"claim": "lead"}))
    large = _idx(Relationship(id="rl", source="a", target="b", relation_type="role",
                              valid_from="2018", attributes={"claim": "lead"}))
    id_map = {"a": "a", "b": "b"}
    merged, conflicts = reconcile_edges(small, large, id_map, MergeConfig())
    assert len(merged) == 2                          # both versions kept
    assert conflicts == []                           # same claim -> not a conflict
    assert any(r.attributes.get("current") for r in merged.values())
    latest = next(r for r in merged.values() if r.attributes.get("current"))
    assert latest.timestamp == "2023"                # newest is current


def test_contradiction_preserved_as_conflict():
    small = _idx(Relationship(id="rs", source="a", target="b", relation_type="status",
                              attributes={"claim": "active"}))
    large = _idx(Relationship(id="rl", source="a", target="b", relation_type="status",
                              attributes={"claim": "inactive"}))
    id_map = {"a": "a", "b": "b"}
    merged, conflicts = reconcile_edges(small, large, id_map, MergeConfig())
    assert len(merged) == 2                          # both claims kept, not overwritten
    assert len(conflicts) == 1
    assert conflicts[0].kind == ConflictKind.CONTRADICTORY_RELATIONSHIP
    assert set(conflicts[0].member_ids) == {"rs", "rl"}
