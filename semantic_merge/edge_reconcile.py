"""Relationship (edge) reconciliation.

After entities are fused, edges must be re-pointed at canonical endpoints and
de-duplicated, while *preserving contradictions* as conflict sets rather than
overwriting them.

Steps:
  1. **remap endpoints** of every relationship through the entity ``id_map`` to
     canonical ids;
  2. **group** relationships by ``(source, target, relation_type)``;
  3. within a group, **merge compatible** relationships — union evidence
     (``text_unit_ids``, provenance), combine weights;
  4. **version temporal updates** — when two edges describe the same fact at
     different times, keep both as an ordered version chain (via
     ``valid_from``/``valid_to``) rather than clobbering the older one;
  5. **preserve contradictory** relationships (same endpoints+type but
     incompatible claims) as :class:`~semantic_merge.schema.ConflictSet`.

Invariant: evidence is never silently overwritten. A merge that loses a
``text_unit_id`` or drops a contradicting edge is incorrect.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schema import (
    ConflictSet,
    Entity,
    MergeConfig,
    Relationship,
    SemanticIndex,
)


def reconcile_edges(
    index_small: SemanticIndex,
    index_large: SemanticIndex,
    id_map: Dict[str, str],
    config: MergeConfig,
) -> Tuple[Dict[str, Relationship], List[ConflictSet]]:
    """Remap, group, and reconcile relationships from both indexes.

    Returns:
      * ``merged_relationships`` — canonical relationship id -> :class:`Relationship`;
      * ``conflicts``            — preserved contradictory-edge conflict sets.
    """
    raise NotImplementedError(
        "TODO(codex task 1): implement edge remap + group + reconcile + conflict preservation"
    )
