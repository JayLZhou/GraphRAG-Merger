"""Unit tests for conflict-aware entity fusion.

To implement (codex task 1):
  * high-confidence bridge fuses two entities into one canonical id;
  * fused entity unions aliases, text_unit_ids, and provenance (no evidence loss);
  * low-confidence pair stays as two separate entities;
  * ambiguous pair is NOT fused and produces an ambiguity/conflict record;
  * id_map maps every original entity id to a canonical id.
"""

import pytest


def test_high_confidence_fuses():
    pytest.skip("TODO(codex task 1): implement fusion test")


def test_fusion_preserves_evidence():
    pytest.skip("TODO(codex task 1): implement evidence-union test")


def test_low_confidence_stays_separate():
    pytest.skip("TODO(codex task 1): implement no-fuse test")


def test_ambiguous_pair_preserved():
    pytest.skip("TODO(codex task 1): implement ambiguity-preservation test")
