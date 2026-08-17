from __future__ import annotations

from app import redis_store

_CHICKEN = {"id": "chicken_breast", "name_en": "Chicken breast", "food_group": "meat", "states": {"raw": {}}}
_BROCCOLI = {"id": "broccoli", "name_en": "Broccoli", "food_group": "vegetable", "states": {"raw": {}}}


def test_set_and_get_ingredient(fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    assert redis_store.get_ingredient("chicken_breast") == _CHICKEN


def test_get_ingredient_missing(fake_redis):
    assert redis_store.get_ingredient("nonexistent") is None


def test_list_ingredient_keys(fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_ingredient("broccoli", _BROCCOLI)
    assert set(redis_store.list_ingredient_keys()) == {"chicken_breast", "broccoli"}


def test_list_slugs_by_group(fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_ingredient("broccoli", _BROCCOLI)
    assert redis_store.list_slugs_by_group("meat") == ["chicken_breast"]
    assert redis_store.list_slugs_by_group("fish") == []


def test_set_and_get_relationship(fake_redis):
    data = {"raw_id": "chicken_breast", "cooking_method": "grilled", "yield_factor": 0.75}
    redis_store.set_relationship("chicken_breast", "grilled", data)
    assert redis_store.get_relationship("chicken_breast", "grilled") == data


def test_list_relationship_keys(fake_redis):
    redis_store.set_relationship("chicken_breast", "grilled", {"raw_id": "chicken_breast", "cooking_method": "grilled", "yield_factor": 0.75})
    redis_store.set_relationship("chicken_breast", "boiled", {"raw_id": "chicken_breast", "cooking_method": "boiled", "yield_factor": 0.85})
    assert set(redis_store.list_relationship_keys()) == {("chicken_breast", "grilled"), ("chicken_breast", "boiled")}


def test_set_and_get_recipe(fake_redis):
    recipe = {
        "id": "raclette",
        "name_en": "traditional raclette",
        "name_fr": "raclette traditionnelle",
        "components": [
            {"ingredient_id": "potato", "weight_g": 200, "cooking_method": "boiled"},
            {"ingredient_id": "raclette_cheese", "weight_g": 100, "cooking_method": "grilled"},
        ],
    }
    redis_store.set_recipe("raclette", recipe)
    assert redis_store.get_recipe("raclette") == recipe
    assert redis_store.get_recipe("nonexistent") is None


def test_list_recipe_keys(fake_redis):
    redis_store.set_recipe("raclette", {"id": "raclette", "components": []})
    redis_store.set_recipe("tartiflette", {"id": "tartiflette", "components": []})
    assert set(redis_store.list_recipe_keys()) == {"raclette", "tartiflette"}


def test_set_unlinked_mapping(fake_redis):
    redis_store.set_mapping({"source": "ciqual", "source_id": "12345", "label": "Poulet rôti"})
    result = redis_store.get_mapping("ciqual", "12345")
    assert result["source_id"] == "12345"
    _, total = redis_store.list_unlinked_mappings()
    assert total == 1


def test_link_mapping_removes_from_unlinked(fake_redis):
    redis_store.set_mapping({"source": "ciqual", "source_id": "12345", "label": "Poulet rôti"})
    redis_store.link_mapping_in_redis("ciqual", "12345", "chicken_breast", "manual", 1.0, None)
    _, total = redis_store.list_unlinked_mappings()
    assert total == 0
    linked = redis_store.get_mapping("ciqual", "12345")
    assert linked["canonical_ingredient_id"] == "chicken_breast"


def test_list_unlinked_mappings_pagination(fake_redis):
    for i in range(5):
        redis_store.set_mapping({"source": "ciqual", "source_id": str(i), "label": f"Food {i}"})
    page, total = redis_store.list_unlinked_mappings(offset=0, limit=3)
    assert total == 5
    assert len(page) == 3


def test_get_dashboard_stats(fake_redis):
    redis_store.set_ingredient("chicken_breast", {**_CHICKEN, "name_fr": "Blanc de poulet"})
    redis_store.set_ingredient("broccoli", _BROCCOLI)
    redis_store.set_mapping({"source": "ciqual", "source_id": "1", "label": "Poulet"})
    redis_store.set_mapping({"source": "ciqual", "source_id": "2", "label": "Composite", "canonical_ingredient_id": "_composite"})
    redis_store.link_mapping_in_redis("ciqual", "1", "chicken_breast", "manual", 1.0, None)
    redis_store.set_relationship("chicken_breast", "grilled", {"raw_id": "chicken_breast", "cooking_method": "grilled", "yield_factor": 0.75})

    stats = redis_store.get_dashboard_stats()

    assert stats["ingredients"]["total"] == 2
    assert stats["ingredients"]["with_name_fr"] == 1
    assert stats["ingredients"]["with_name_en"] == 2
    assert stats["relationships"]["total"] == 1
    ciqual = stats["mappings"]["ciqual"]
    assert ciqual["total"] == 2
    assert ciqual["linked"] == 1
    assert ciqual["unlinked"] == 0
    assert ciqual["dismissed"] == 1
    assert "off" not in stats["mappings"]
