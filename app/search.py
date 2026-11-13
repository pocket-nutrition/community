"""Accent-insensitive, ranked ingredient search.

Field coverage mirrors the knowledge editor's search (id, names, EN/FR
aliases); diacritics folding, multi-token AND matching and relevance
ranking are portal additions.
"""
from __future__ import annotations

import unicodedata
from typing import Any

_RANK_EXACT = 0
_RANK_PREFIX = 1
_RANK_SUBSTRING = 2
_RANK_ALIAS = 3


def normalize(s: str) -> str:
    """Lowercase and strip diacritics so that 'epinard' matches 'épinard'."""
    decomposed = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _rank(data: dict[str, Any], tokens: list[str], query: str) -> int | None:
    """Return the relevance rank of an ingredient for a query, or None if no match."""
    names = [normalize(data["id"]), normalize(data["name_en"])]
    if data.get("name_fr"):
        names.append(normalize(data["name_fr"]))
    aliases = [
        normalize(a)
        for a in (data.get("aliases_en") or []) + (data.get("aliases_fr") or [])
    ]
    haystack = names + aliases
    if not all(any(token in field for field in haystack) for token in tokens):
        return None
    if any(name == query for name in names):
        return _RANK_EXACT
    if any(name.startswith(query) for name in names):
        return _RANK_PREFIX
    if all(any(token in name for name in names) for token in tokens):
        return _RANK_SUBSTRING
    return _RANK_ALIAS


def search_ingredients(ingredients: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    """Filter and rank ingredient dicts against a free-text query.

    Every query token must match (AND) in the id, names or aliases.
    Results are ordered: exact name/id match, then name/id prefix, then
    name/id substring, then alias-only matches — alphabetical within a rank.
    """
    tokens = normalize(q).split()
    if not tokens:
        return ingredients
    query = " ".join(tokens)
    ranked = [
        (rank, normalize(data["name_en"]), data)
        for data in ingredients
        if (rank := _rank(data, tokens, query)) is not None
    ]
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [data for _, _, data in ranked]
