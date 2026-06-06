"""Generate synthetic semantic indexes with planted, controllable phenomena.

The generator plants known ground-truth phenomena so evaluation metrics are
exact (no labeling):

  * **duplicated entities**          — same entity in both indexes (exact-name
    and alias-variation forms);
  * **same-name different entities** — identical name, different type;
  * **relationship conflicts**       — contradictory claims on the same edge;
  * **temporal updates**             — same claim, newer timestamp (versioned);
  * **stale summaries**              — community summaries touched by the merge.

Everything is deterministic (``random.Random(seed)``) and offline.
"""

from __future__ import annotations

import os
import sys

# Support both `python -m experiments.make_synthetic_indexes` and direct execution.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import random

from semantic_merge.schema import (
    Community,
    Entity,
    Relationship,
    SemanticIndex,
    Summary,
    TextUnit,
)

_FIRST = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Heidi",
          "Ivan", "Judy", "Mallory", "Niaj", "Olivia", "Peggy", "Rupert", "Sybil"]
_LAST = ["Smith", "Jones", "Brown", "Taylor", "Wilson", "Davies", "Evans",
         "Walker", "Roberts", "Wright", "Hughes", "Green", "Hall", "Wood"]
_ORG = ["Acme", "Globex", "Initech", "Umbrella", "Soylent", "Hooli", "Stark",
        "Wayne", "Wonka", "Cyberdyne", "Tyrell", "Aperture", "Massive", "Vault"]
_ORG_SUFFIX = ["Corporation", "Industries", "Holdings", "Systems", "Labs"]
_REL = ["works_at", "located_in", "partner_of", "founded", "advises"]


@dataclass
class GroundTruth:
    """Planted answers for an evaluation pair (ids are original, pre-namespacing)."""

    duplicate_groups: Dict[str, List[str]] = field(default_factory=dict)
    same_name_distinct: List[Tuple[str, str]] = field(default_factory=list)
    relationship_conflicts: List[Tuple[str, str]] = field(default_factory=list)
    stale_summaries: List[str] = field(default_factory=list)


def _person(rng: random.Random) -> Tuple[str, str]:
    return f"{rng.choice(_FIRST)} {rng.choice(_LAST)}", "person"


def _org(rng: random.Random) -> Tuple[str, str]:
    return f"{rng.choice(_ORG)} {rng.choice(_ORG_SUFFIX)}", "org"


def _alias_variation(name: str, etype: str) -> str:
    """A surface variation of ``name`` that differs as an exact string."""
    if etype == "person":
        first, last = name.split(" ", 1)
        return f"{first[0]}. {last}"          # "Alice Smith" -> "A. Smith"
    return name.split(" ", 1)[0] + " Corp"     # "Acme Industries" -> "Acme Corp"


def build_synthetic_pair(
    n_entities: int = 100,
    overlap: float = 0.3,
    conflict_rate: float = 0.1,
    seed: int = 0,
) -> Tuple[SemanticIndex, SemanticIndex, GroundTruth]:
    """Build two synthetic indexes plus ground truth.

    Args:
        n_entities: entity count of the larger index.
        overlap: fraction of large entities also present in the small index.
        conflict_rate: fraction of shared entities given conflicting/temporal evidence.
        seed: RNG seed for reproducibility.
    """
    rng = random.Random(seed)
    small = SemanticIndex(name="small")
    large = SemanticIndex(name="large")
    gt = GroundTruth()

    # Unique name pools so the only intentional name collisions are the planted
    # same-name-distinct pairs (random collisions would create real ambiguity
    # that the merger correctly refuses to fuse, muddying the metrics).
    person_pool = [f"{f} {l}" for f in _FIRST for l in _LAST]
    org_pool = [f"{o} {s}" for o in _ORG for s in _ORG_SUFFIX]
    rng.shuffle(person_pool)
    rng.shuffle(org_pool)

    def _unique_entity(i: int) -> Tuple[str, str]:
        if rng.random() < 0.7 and person_pool:
            return person_pool.pop(), "person"
        if org_pool:
            return org_pool.pop(), "org"
        if person_pool:
            return person_pool.pop(), "person"
        return f"Entity {i} Group", "org"  # pools exhausted (very large n)

    # ---- large index: entities, communities, text units --------------------
    large_entities: List[Entity] = []
    for i in range(n_entities):
        name, etype = _unique_entity(i)
        tu_id = f"L_tu{i}"
        large.text_units[tu_id] = TextUnit(id=tu_id, text=f"...{name}...")
        ent = Entity(id=f"L{i}", name=name, type=etype, text_unit_ids=[tu_id])
        large.entities[ent.id] = ent
        large_entities.append(ent)

    csize = 8
    comm_of: Dict[str, str] = {}
    for c, start in enumerate(range(0, n_entities, csize)):
        members = [e.id for e in large_entities[start:start + csize]]
        cid = f"c{c}"
        large.communities[cid] = Community(id=cid, entity_ids=members, title=f"Community {c}")
        for m in members:
            comm_of[m] = cid
        large.summaries[f"sm{c}"] = Summary(
            id=f"sm{c}", community_id=cid, text=f"Summary of community {c}.",
            coverage=1.0, source_hash=f"h{c}",
        )

    # a few intra-community relationships in the large index
    for c, comm in enumerate(large.communities.values()):
        ms = comm.entity_ids
        for k in range(min(3, len(ms) - 1)):
            r = Relationship(id=f"Lr{c}_{k}", source=ms[k], target=ms[k + 1],
                             relation_type=rng.choice(_REL))
            large.relationships[r.id] = r

    # ---- shared duplicates in the small index ------------------------------
    n_shared = int(n_entities * overlap)
    shared_targets = rng.sample(large_entities, k=min(n_shared, len(large_entities)))
    shared_pairs: List[Tuple[str, str]] = []  # (small_id, large_id)
    for j, tgt in enumerate(shared_targets):
        if j % 5 < 2:  # ~40% exact-name duplicates
            sname, aliases = tgt.name, []
        else:          # ~60% alias-variation duplicates
            sname, aliases = _alias_variation(tgt.name, tgt.type or "person"), [tgt.name]
        sid = f"S{j}"
        tu_id = f"S_tu{j}"
        small.text_units[tu_id] = TextUnit(id=tu_id, text=f"...{sname}...")
        small.entities[sid] = Entity(id=sid, name=sname, type=tgt.type,
                                     aliases=aliases, text_unit_ids=[tu_id])
        gt.duplicate_groups[tgt.id] = [tgt.id, sid]
        shared_pairs.append((sid, tgt.id))

    # ---- same-name different-entity (must NOT fuse) ------------------------
    n_distinct = max(2, n_entities // 20)
    for j in range(n_distinct):
        tgt = large_entities[j]
        other_type = "org" if tgt.type == "person" else "person"
        sid = f"SD{j}"
        small.entities[sid] = Entity(id=sid, name=tgt.name, type=other_type)
        gt.same_name_distinct.append((sid, tgt.id))

    # ---- small-only new entities (boundary attachments) --------------------
    for j in range(max(2, n_entities // 20)):
        name, etype = _org(rng) if rng.random() < 0.5 else _person(rng)
        sid = f"SN{j}"
        small.entities[sid] = Entity(id=sid, name=name + f" New{j}", type=etype)
        if shared_pairs:
            ssrc = rng.choice(shared_pairs)[0]
            small.relationships[f"SNr{j}"] = Relationship(
                id=f"SNr{j}", source=ssrc, target=sid, relation_type="advises")

    # ---- relationship conflicts + temporal updates among shared pairs ------
    n_conf = int(len(shared_pairs) * conflict_rate)
    affected_comms = set()
    for j in range(n_conf):
        (sa, la), (sb, lb) = shared_pairs[2 * j % len(shared_pairs)], shared_pairs[(2 * j + 1) % len(shared_pairs)]
        if la == lb:
            continue
        lr = Relationship(id=f"Lconf{j}", source=la, target=lb, relation_type="status",
                          attributes={"claim": "active"})
        sr = Relationship(id=f"Sconf{j}", source=sa, target=sb, relation_type="status",
                          attributes={"claim": "inactive"})
        large.relationships[lr.id] = lr
        small.relationships[sr.id] = sr
        gt.relationship_conflicts.append((lr.id, sr.id))
        affected_comms.update(c for c in (comm_of.get(la), comm_of.get(lb)) if c)

        # temporal update on a different relation type (same claim, newer time)
        large.relationships[f"Ltime{j}"] = Relationship(
            id=f"Ltime{j}", source=la, target=lb, relation_type="role",
            valid_from="2018-01-01", attributes={"claim": "lead"})
        small.relationships[f"Stime{j}"] = Relationship(
            id=f"Stime{j}", source=sa, target=sb, relation_type="role",
            valid_from="2023-01-01", attributes={"claim": "lead"})

    # communities touched by shared/conflicted entities become stale
    for sid, lid in shared_pairs:
        if comm_of.get(lid):
            affected_comms.add(comm_of[lid])
    gt.stale_summaries = sorted(affected_comms)

    return small, large, gt


def build_synthetic_k(
    k: int = 4,
    universe: int = 60,
    appear_prob: float = 0.6,
    seed: int = 0,
) -> Tuple[List[SemanticIndex], int]:
    """Build ``k`` overlapping shards drawn from a shared universe of entities.

    Each of ``universe`` distinct real entities appears in each shard with
    probability ``appear_prob`` (half the time as an alias variation), so the
    same entity recurs across shards and a correct multi-index merge collapses
    them back toward ``universe`` entities. Shards reuse ids on purpose (the
    merger namespaces per merge), exercising collision handling.

    Returns ``(indexes, universe)``; ``universe`` is the ideal final entity count.
    """
    rng = random.Random(seed)
    person_pool = [f"{f} {l}" for f in _FIRST for l in _LAST]
    org_pool = [f"{o} {s}" for o in _ORG for s in _ORG_SUFFIX]
    rng.shuffle(person_pool)
    rng.shuffle(org_pool)

    reals: List[Tuple[str, str]] = []
    for r in range(universe):
        if rng.random() < 0.7 and person_pool:
            reals.append((person_pool.pop(), "person"))
        elif org_pool:
            reals.append((org_pool.pop(), "org"))
        elif person_pool:
            reals.append((person_pool.pop(), "person"))

    indexes: List[SemanticIndex] = []
    for s in range(k):
        idx = SemanticIndex(name=f"shard{s}")
        for r, (name, etype) in enumerate(reals):
            if rng.random() >= appear_prob:
                continue
            if rng.random() < 0.5:
                nm, aliases = name, []
            else:
                nm, aliases = _alias_variation(name, etype), [name]
            eid, tu = f"e{r}", f"tu{r}"
            idx.text_units[tu] = TextUnit(id=tu, text=nm)
            idx.entities[eid] = Entity(id=eid, name=nm, type=etype, aliases=aliases, text_unit_ids=[tu])
        ents = list(idx.entities)
        for c, start in enumerate(range(0, len(ents), 8)):
            cid = f"c{c}"
            idx.communities[cid] = Community(id=cid, entity_ids=ents[start:start + 8], title=f"c{c}")
            idx.summaries[f"sm{c}"] = Summary(id=f"sm{c}", community_id=cid, text=f"shard {s} comm {c}", coverage=1.0)
        indexes.append(idx)
    return indexes, universe


if __name__ == "__main__":  # pragma: no cover
    s, l, g = build_synthetic_pair(seed=0)
    print(f"small={s.n_entities} entities, large={l.n_entities} entities")
    print(f"planted: {len(g.duplicate_groups)} dup groups, "
          f"{len(g.same_name_distinct)} same-name-distinct, "
          f"{len(g.relationship_conflicts)} edge conflicts, "
          f"{len(g.stale_summaries)} stale summaries")
