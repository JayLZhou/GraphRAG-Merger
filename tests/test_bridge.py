"""Unit tests for bridge discovery."""

from semantic_merge.bridge import discover_entity_bridges, score_pair
from semantic_merge.schema import Entity, MergeConfig, SemanticIndex


def _idx(*entities: Entity) -> SemanticIndex:
    idx = SemanticIndex()
    for e in entities:
        idx.add_entity(e)
    return idx


def test_discovers_exact_duplicate():
    small = _idx(Entity(id="s1", name="Alice Smith", type="person"))
    large = _idx(
        Entity(id="l1", name="Alice Smith", type="person"),
        Entity(id="l2", name="Bob Jones", type="person"),
    )
    res = discover_entity_bridges(small, large, MergeConfig())
    best = res.by_source["s1"][0]
    assert best.target_id == "l1"
    assert best.score >= 0.9


def test_alias_match_discovered():
    # "J. Smith" should match "John Smith" via the alias on the small entity.
    small = _idx(Entity(id="s1", name="J. Smith", type="person", aliases=["John Smith"]))
    large = _idx(Entity(id="l1", name="John Smith", type="person"))
    res = discover_entity_bridges(small, large, MergeConfig())
    assert "s1" in res.by_source
    assert res.by_source["s1"][0].target_id == "l1"
    assert res.by_source["s1"][0].score >= MergeConfig().high_confidence_threshold


def test_same_name_different_type_not_high():
    a = Entity(id="s1", name="Apple", type="food")
    b = Entity(id="l1", name="Apple", type="org")
    cand = score_pair(a, b, _idx(a), _idx(b), MergeConfig())
    assert cand.features["type"] == 0.0  # known type mismatch
    assert cand.features["name"] >= 0.9  # names are identical though


def test_blocking_avoids_quadratic():
    small = _idx(*[Entity(id=f"s{i}", name=f"Person{i} Alpha", type="person") for i in range(5)])
    large = _idx(*[Entity(id=f"l{i}", name=f"Other{i} Beta", type="person") for i in range(50)])
    # plant one true match so discovery still finds something
    large.add_entity(Entity(id="match", name="Person0 Alpha", type="person"))
    res = discover_entity_bridges(small, large, MergeConfig())
    assert res.comparisons < small.n_entities * large.n_entities
    assert res.by_source["s0"][0].target_id == "match"
