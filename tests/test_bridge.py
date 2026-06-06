"""Unit tests for bridge discovery.

To implement (codex task 1) — replace the skips with real assertions:
  * exact-name duplicates produce a high-score candidate;
  * alias-only matches ("J. Smith" vs "John Smith") are discovered;
  * same-name / different-type pairs are NOT given a high score;
  * embedding similarity raises the score when embeddings are present;
  * blocking limits the number of pairs actually scored (no quadratic blowup).
"""

import pytest

from semantic_merge.schema import MergeConfig


def test_discovers_exact_duplicate():
    pytest.skip("TODO(codex task 1): implement bridge discovery test")


def test_alias_match_discovered():
    pytest.skip("TODO(codex task 1): implement alias-match test")


def test_same_name_different_type_not_high():
    pytest.skip("TODO(codex task 1): implement type-incompatibility test")


def test_blocking_avoids_quadratic():
    pytest.skip("TODO(codex task 1): implement blocking / comparison-count test")
