"""Tests for certain/possible answering over a conflict-tolerant merged index."""

from semantic_merge import merge_two_indexes, query
from semantic_merge.schema import Entity, MergeConfig, Relationship, SemanticIndex


def _merged_with_conflicts():
    a = SemanticIndex(name="A")
    a.add_entity(Entity(id="a1", name="Alice Smith", type="person"))
    a.add_entity(Entity(id="a2", name="Acme Corporation", type="org"))
    a.add_entity(Entity(id="a3", name="Apple", type="food"))
    a.add_relationship(Relationship(id="ar", source="a1", target="a2",
                                    relation_type="status", attributes={"claim": "active"}))

    b = SemanticIndex(name="B")
    b.add_entity(Entity(id="b1", name="Alice Smith", type="person"))
    b.add_entity(Entity(id="b2", name="Acme Corporation", type="org"))
    b.add_entity(Entity(id="b3", name="Apple", type="org"))  # same name, different type
    b.add_relationship(Relationship(id="br", source="b1", target="b2",
                                    relation_type="status", attributes={"claim": "inactive"}))
    return merge_two_indexes(a, b, MergeConfig(namespace_ids=False))


def test_contested_relationship_has_no_certain_claim():
    m = _merged_with_conflicts()
    ans = query.query_relationship(m, "a1", "a2", "status")
    assert ans["contested"] is True
    assert ans["exists"]["certain"] is True          # the edge holds in every repair
    assert ans["claim"]["certain"] == []             # but no single claim is certain
    assert set(ans["claim"]["possible"]) == {"active", "inactive"}


def test_uncontested_relationship_is_certain():
    a = SemanticIndex(name="A")
    a.add_entity(Entity(id="a1", name="Alice Smith", type="person"))
    a.add_entity(Entity(id="a2", name="Acme Corporation", type="org"))
    a.add_relationship(Relationship(id="ar", source="a1", target="a2",
                                    relation_type="status", attributes={"claim": "active"}))
    b = SemanticIndex(name="B")
    b.add_entity(Entity(id="b1", name="Alice Smith", type="person"))
    b.add_entity(Entity(id="b2", name="Acme Corporation", type="org"))
    m = merge_two_indexes(a, b, MergeConfig(namespace_ids=False))
    ans = query.query_relationship(m, "a1", "a2", "status")
    assert ans["contested"] is False
    assert ans["claim"]["certain"] == ["active"] == ans["claim"]["possible"]


def test_same_name_different_type_is_contested():
    m = _merged_with_conflicts()
    ans = query.query_entity_type(m, "Apple")
    assert ans["contested"] is True
    assert set(ans["type"]["possible"]) == {"food", "org"}
    assert ans["type"]["certain"] == []
