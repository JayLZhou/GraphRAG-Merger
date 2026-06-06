"""Pure-Python text and similarity helpers.

Dependency-free on purpose: name normalization, fuzzy name similarity (with
initial-matching for person names), Jaccard overlap, and cosine similarity for
optional embeddings. Shared by bridge discovery, pruning, the baselines, and
evaluation so they all judge similarity the same way.
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import List, Optional, Sequence, Set

from .schema import Embedding, Entity

_PUNCT = re.compile(r"[^0-9a-z\s]+")
_WS = re.compile(r"\s+")


def normalize_name(name: Optional[str]) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not name:
        return ""
    text = _PUNCT.sub(" ", name.lower())
    return _WS.sub(" ", text).strip()


def tokens(name: Optional[str]) -> List[str]:
    """Normalized token list for ``name``."""
    norm = normalize_name(name)
    return norm.split(" ") if norm else []


def _token_match(a: str, b: str) -> float:
    """Similarity of two single tokens in ``[0, 1]``.

    Handles the person-name initial case ("a" ~ "alice") explicitly so alias
    variations score high without matching unrelated tokens.
    """
    if a == b:
        return 1.0
    # initial vs full first name ("a" ~ "alice")
    if len(a) == 1 and b.startswith(a):
        return 0.9
    if len(b) == 1 and a.startswith(b):
        return 0.9
    # shared prefix / substring
    if a.startswith(b) or b.startswith(a):
        return 0.7
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Token-aware similarity between two names in ``[0, 1]``.

    Greedily matches each token of the smaller set to its best counterpart in
    the other, averaging over the larger token count so missing tokens are
    penalized.
    """
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    remaining = list(large)
    total = 0.0
    for tok in small:
        if not remaining:
            break
        best_i, best_s = -1, -1.0
        for i, other in enumerate(remaining):
            s = _token_match(tok, other)
            if s > best_s:
                best_i, best_s = i, s
        total += best_s
        remaining.pop(best_i)
    return total / max(len(ta), len(tb))


def best_label_similarity(a: Entity, b: Entity) -> float:
    """Best :func:`name_similarity` over all (name + alias) label pairs.

    Entities carry aliases precisely so a surface variant ("Acme Corp") can be
    matched against another's canonical label ("Acme Industries"); scoring only
    the canonical names would miss exactly those alias-variation duplicates.
    """
    labels_a = [a.name, *a.aliases]
    labels_b = [b.name, *b.aliases]
    best = 0.0
    for la in labels_a:
        for lb in labels_b:
            s = name_similarity(la, lb)
            if s > best:
                best = s
    return best


def jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard overlap of two sets in ``[0, 1]`` (empty/empty -> 0.0)."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def alias_token_set(entity: Entity) -> Set[str]:
    """All normalized tokens drawn from an entity's name and aliases."""
    toks: Set[str] = set()
    for label in [entity.name, *entity.aliases]:
        toks.update(tokens(label))
    return toks


def alias_overlap(a: Entity, b: Entity) -> float:
    """Token-level Jaccard overlap of two entities' name+alias vocabularies."""
    return jaccard(alias_token_set(a), alias_token_set(b))


def cosine(a: Optional[Sequence[float]], b: Optional[Sequence[float]]) -> float:
    """Cosine similarity mapped to ``[0, 1]``; ``None``/length-mismatch -> 0.0."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    cos = dot / (na * nb)
    return max(0.0, min(1.0, (cos + 1.0) / 2.0))


def intervals_overlap(
    a_from: Optional[str],
    a_to: Optional[str],
    b_from: Optional[str],
    b_to: Optional[str],
) -> bool:
    """Whether two optional [from, to] validity intervals can co-refer.

    Missing bounds are treated as open (-inf / +inf). String timestamps are
    compared lexicographically, which is correct for ISO-8601 dates.
    """
    lo_a = a_from if a_from is not None else ""
    hi_a = a_to if a_to is not None else "~"  # '~' > digits/letters in ASCII
    lo_b = b_from if b_from is not None else ""
    hi_b = b_to if b_to is not None else "~"
    return lo_a <= hi_b and lo_b <= hi_a
