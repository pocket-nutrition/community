from __future__ import annotations

from app import redis_store

_CHICKEN = {"id": "chicken_breast", "name_en": "Chicken breast", "food_group": "meat", "states": {"raw": {}}}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_dashboard_page(client):
    r = client.get("/ui/dashboard")
    assert r.status_code == 200
    assert b"Dashboard" in r.content
    assert b"Ingredients" in r.content
    assert b"CIQUAL" in r.content


def test_list_ingredients_empty(client):
    assert client.get("/api/ingredients").json() == []


def test_list_ingredients(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    data = client.get("/api/ingredients").json()
    assert len(data) == 1
    assert data[0]["id"] == "chicken_breast"


def test_list_ingredients_food_group_filter(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_ingredient("broccoli", {"id": "broccoli", "name_en": "Broccoli", "food_group": "vegetable", "states": {"raw": {}}})
    data = client.get("/api/ingredients?food_group=meat").json()
    assert [i["id"] for i in data] == ["chicken_breast"]


def test_get_ingredient_not_found(client):
    assert client.get("/api/ingredients/nonexistent").status_code == 404


def test_get_ingredient_with_relationships(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_relationship("chicken_breast", "grilled", {
        "raw_id": "chicken_breast", "cooking_method": "grilled", "yield_factor": 0.75
    })
    body = client.get("/api/ingredients/chicken_breast").json()
    assert body["id"] == "chicken_breast"
    assert len(body["cooking_relationships"]) == 1
    assert body["cooking_relationships"][0]["cooking_method"] == "grilled"


def test_resolve_mapping_not_found(client):
    assert client.get("/api/ingredients/resolve/ciqual/99999").status_code == 404


def test_resolve_mapping_unlinked(client, fake_redis):
    redis_store.set_mapping({"source": "ciqual", "source_id": "12345", "label": "Poulet"})
    assert client.get("/api/ingredients/resolve/ciqual/12345").status_code == 409


def test_resolve_mapping_linked(client, fake_redis):
    redis_store.set_mapping({
        "source": "ciqual", "source_id": "12345",
        "canonical_ingredient_id": "chicken_breast", "label": "Poulet"
    })
    body = client.get("/api/ingredients/resolve/ciqual/12345").json()
    assert body["canonical_ingredient_id"] == "chicken_breast"


def test_list_relationships_empty(client):
    assert client.get("/api/relationships").json() == []


def test_list_relationships_filtered_by_method(client, fake_redis):
    redis_store.set_relationship("chicken_breast", "grilled", {
        "raw_id": "chicken_breast", "cooking_method": "grilled", "yield_factor": 0.75
    })
    redis_store.set_relationship("chicken_breast", "boiled", {
        "raw_id": "chicken_breast", "cooking_method": "boiled", "yield_factor": 0.85
    })
    data = client.get("/api/relationships?cooking_method=grilled").json()
    assert len(data) == 1
    assert data[0]["cooking_method"] == "grilled"


def test_admin_status(client):
    body = client.get("/admin/status").json()
    assert "ingredient_count" in body
    assert "relationship_count" in body
