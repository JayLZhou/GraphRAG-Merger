"""Unit tests for the local repair planner.

To implement (codex task 1):
  * an unchanged community drifts ~0 and resolves to NOOP;
  * a small membership change resolves to PATCH/REGENERATE_SUMMARY, not rebuild;
  * a large boundary/conflict change escalates to LOCAL_RECLUSTER / REBUILD;
  * the chosen action is the cheapest satisfying drift<=threshold and
    coverage>=threshold;
  * drift increases monotonically with each weighted component.
"""

import pytest

from semantic_merge.schema import MergeConfig, RepairAction


def test_unchanged_community_is_noop():
    pytest.skip("TODO(codex task 1): implement NOOP test")


def test_small_change_patches_summary():
    pytest.skip("TODO(codex task 1): implement patch/regenerate test")


def test_large_change_escalates():
    pytest.skip("TODO(codex task 1): implement escalation test")


def test_chooses_cheapest_under_threshold():
    pytest.skip("TODO(codex task 1): implement cheapest-action test")
