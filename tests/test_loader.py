"""Round-trip test for JSON (de)serialization."""

from experiments.make_synthetic_indexes import build_synthetic_pair
from semantic_merge.loader import index_from_dict, index_to_dict, load_index_from_json, save_index_to_json


def _counts(idx):
    return (len(idx.text_units), idx.n_entities, idx.n_relationships,
            len(idx.communities), len(idx.summaries))


def test_dict_round_trip():
    _, large, _ = build_synthetic_pair(n_entities=40, seed=5)
    back = index_from_dict(index_to_dict(large))
    assert _counts(back) == _counts(large)
    # a specific entity survives intact.
    eid = next(iter(large.entities))
    assert back.entities[eid].name == large.entities[eid].name
    assert back.entities[eid].type == large.entities[eid].type


def test_json_file_round_trip(tmp_path):
    _, large, _ = build_synthetic_pair(n_entities=40, seed=6)
    path = tmp_path / "index.json"
    save_index_to_json(large, path)
    back = load_index_from_json(path)
    assert _counts(back) == _counts(large)
