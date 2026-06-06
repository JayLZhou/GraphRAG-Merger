"""Unit tests for conflict-aware entity fusion."""

from semantic_merge.bridge import discover_entity_bridges
from semantic_merge.entity_merge import merge_entities
from semantic_merge.prune import robust_semantic_prune
from semantic_merge.schema import ConflictKind, Entity, MergeConfig, SemanticIndex


def _run(small: SemanticIndex, large: SemanticIndex, config: MergeConfig):
    bridges = discover_entity_bridges(small, large, config)
    pruned = robust_semantic_prune(bridges, small, large, config)
    return merge_entities(small, large, pruned, config)


def _idx(*entities: Entity) -> SemanticIndex:
    idx = SemanticIndex()
    for e in entities:
        idx.add_entity(e)
    return idx


def test_high_confidence_fuses():
    small = _idx(Entity(id="s1", name="Alice Smith", type="person"))
    large = _idx(
        Entity(id="l1", name="Alice Smith", type="person"),
        Entity(id="l2", name="Bob Jones", type="person"),
    )
    merged, id_map, _ = _run(small, large, MergeConfig())
    assert id_map["s1"] == id_map["l1"]      # fused
    assert len(merged) == 2                  # l1(+s1), l2


def test_fusion_preserves_evidence():
    small = _idx(Entity(id="s1", name="J. Smith", type="person",
                        aliases=["John Smith"], text_unit_ids=["s_t"]))
    large = _idx(Entity(id="l1", name="John Smith", type="person", text_unit_ids=["l_t"]))
    merged, id_map, _ = _run(small, large, MergeConfig())
    fused = merged[id_map["s1"]]
    assert set(fused.text_unit_ids) == {"s_t", "l_t"}          # evidence unioned
    assert "J. Smith" in fused.aliases                          # alias preserved
    assert any(src["id"] == "s1" for src in fused.provenance["sources"])


def test_low_confidence_stays_separate():
    small = _idx(Entity(id="s1", name="Zeta Quux", type="person"))
    large = _idx(Entity(id="l1", name="Omega Plugh", type="person"))
    merged, id_map, _ = _run(small, large, MergeConfig())
    assert id_map["s1"] != id_map["l1"]      # not fused
    assert len(merged) == 2


def test_ambiguous_pair_preserved():
    # One small entity matches two identically-named large entities -> ambiguous.
    small = _idx(Entity(id="s1", name="Acme Corp", type="org"))
    large = _idx(
        Entity(id="l1", name="Acme Corp", type="org"),
        Entity(id="l2", name="Acme Corp", type="org"),
    )
    merged, id_map, conflicts = _run(small, large, MergeConfig())
    # s1 was not auto-fused into either
    assert id_map["s1"] == "s1"
    assert any(c.kind == ConflictKind.AMBIGUOUS_BRIDGE and "s1" in c.member_ids for c in conflicts)
