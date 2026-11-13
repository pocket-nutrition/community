from __future__ import annotations

from app.search import normalize, search_ingredients


def _ing(id: str, name_en: str, **extra) -> dict:
    return {"id": id, "name_en": name_en, "food_group": "other", "states": {"raw": {}}, **extra}


_SPINACH = _ing("spinach", "spinach", name_fr="épinard")
_CHICKEN = _ing("chicken_breast", "chicken breast")
_MILK = _ing("milk", "milk")
_MILKSHAKE = _ing("milkshake", "milkshake")
_COCONUT_MILK = _ing("coconut_milk", "coconut milk")
_BUTTER = _ing("butter", "butter", aliases_en=["milk fat"])


def test_normalize_strips_accents_and_lowercases():
    assert normalize("Épinard") == "epinard"
    assert normalize("crème fraîche") == "creme fraiche"


def test_empty_query_returns_input_unchanged():
    items = [_CHICKEN, _SPINACH]
    assert search_ingredients(items, "") == items
    assert search_ingredients(items, "   ") == items


def test_accent_insensitive_both_ways():
    assert search_ingredients([_SPINACH, _CHICKEN], "epinard") == [_SPINACH]
    assert search_ingredients([_SPINACH, _CHICKEN], "ÉPINARD") == [_SPINACH]


def test_alias_match():
    results = search_ingredients([_BUTTER, _CHICKEN], "milk fat")
    assert results == [_BUTTER]


def test_multi_token_all_must_match_in_any_order():
    thigh = _ing("chicken_thigh", "chicken thigh")
    assert search_ingredients([_CHICKEN, thigh], "chicken breast") == [_CHICKEN]
    assert search_ingredients([_CHICKEN, thigh], "breast chicken") == [_CHICKEN]
    assert search_ingredients([_CHICKEN, thigh], "chicken pork") == []


def test_relevance_ranking_exact_prefix_substring_alias():
    items = [_BUTTER, _COCONUT_MILK, _MILKSHAKE, _MILK]
    results = search_ingredients(items, "milk")
    assert [i["id"] for i in results] == ["milk", "milkshake", "coconut_milk", "butter"]


def test_search_matches_id():
    assert search_ingredients([_CHICKEN, _MILK], "chicken_bre") == [_CHICKEN]
