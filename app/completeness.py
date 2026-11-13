"""Data-confidence score for the public ingredient list and detail page.

Mirrors the identity/sources/cooking scoring the knowledge editor uses to
prioritise its curation backlog, reframed here as a visitor-facing "how
well-documented is this ingredient" signal rather than a to-do list.
"""
from __future__ import annotations

from typing import Any, NamedTuple

SOURCES: tuple[str, ...] = ("ciqual", "mccance", "usda", "usda_foundation", "usda_sr")


class MappingTally(NamedTuple):
    total: int = 0
    verified: int = 0


class Completeness(NamedTuple):
    overall: int
    profile: int
    sources: int
    cooking: int
    mapping_count: int
    verified_mapping_count: int
    needs_cooking: bool


def is_verified_mapping(mapping: dict[str, Any]) -> bool:
    return mapping.get("match_method") == "manual" and mapping.get("confidence") == 1.0


def ingredient_needs_cooking(ingredient: dict[str, Any]) -> bool:
    return any(state != "raw" for state in (ingredient.get("states") or {}))


def _score_profile(ingredient: dict[str, Any]) -> int:
    score = 0
    if ingredient.get("name_fr"):
        score += 40
    if ingredient.get("typical_state"):
        score += 30
    if ingredient.get("can_eat_raw") is not None:
        score += 15
    if ingredient.get("can_eat_cooked") is not None:
        score += 15
    return min(score, 100)


def _score_sources(tally: MappingTally) -> int:
    if tally.verified >= 1:
        return 100
    if tally.total >= 2:
        return 70
    if tally.total == 1:
        return 45
    return 0


def _score_cooking(needs: bool, relationship_count: int) -> int:
    if not needs:
        return 100
    if relationship_count == 0:
        return 0
    if relationship_count == 1:
        return 60
    return 100


def build_completeness(
    ingredient: dict[str, Any],
    tally: MappingTally,
    relationship_count: int,
) -> Completeness:
    profile = _score_profile(ingredient)
    sources = _score_sources(tally)
    needs = ingredient_needs_cooking(ingredient)
    cooking = _score_cooking(needs, relationship_count)
    overall = (profile + sources + cooking) // 3
    return Completeness(
        overall=overall,
        profile=profile,
        sources=sources,
        cooking=cooking,
        mapping_count=tally.total,
        verified_mapping_count=tally.verified,
        needs_cooking=needs,
    )
