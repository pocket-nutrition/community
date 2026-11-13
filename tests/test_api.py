from __future__ import annotations

from unittest.mock import patch

from app import redis_store

_CHICKEN = {"id": "chicken_breast", "name_en": "Chicken breast", "food_group": "meat", "states": {"raw": {}}}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_root_redirects_to_ingredients(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/ui/ingredients"


def test_stats_page(client):
    r = client.get("/ui/stats")
    assert r.status_code == 200
    assert b"Stats" in r.content
    assert b"CIQUAL" in r.content


def test_dashboard_redirects_to_stats(client):
    r = client.get("/ui/dashboard", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/ui/stats"


def test_nav_is_minimal_and_footer_links_stats(client):
    html = client.get("/ui/ingredients").text
    nav = html.split('aria-label="Food Dataset">')[1].split("</nav>")[0]
    assert "/ui/ingredients" in nav
    assert "/ui/dashboard" not in nav
    footer = html.split('<footer class="site-footer">')[1].split("</footer>")[0]
    assert "/ui/stats" in footer
    assert "/ui/relationships" not in html


def test_group_bar_lists_every_site_and_marks_the_food_dataset(client):
    html = client.get("/ui/ingredients").text
    group_bar = html.split('aria-label="Pocket Nutrition sites">')[1].split("</nav>")[0]
    assert 'href="/ui/ingredients" aria-current="true">Food Dataset' in group_bar
    for site in ("Website", "Docs", "API", "GitHub"):
        assert site in group_bar


def test_knowledge_editor_page_redirects_to_the_docs_guide(client):
    r = client.get("/ui/knowledge-editor", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://website.pocketnutrition.org/docs/contribute/knowledge-editor"


def test_relationships_ui_page_removed(client):
    assert client.get("/ui/relationships").status_code == 404


def test_ui_search_accent_insensitive_with_ranking(client, fake_redis):
    redis_store.set_ingredient("spinach", {
        "id": "spinach", "name_en": "spinach", "name_fr": "épinard",
        "food_group": "vegetable", "states": {"raw": {}},
    })
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.get("/ui/ingredients/search?q=epinard")
    assert "spinach" in r.text
    assert "chicken_breast" not in r.text
    assert r.headers["HX-Push-Url"] == "/ui/ingredients?q=epinard"


def test_ui_search_combines_query_and_group(client, fake_redis):
    redis_store.set_ingredient("spinach", {
        "id": "spinach", "name_en": "spinach", "name_fr": "épinard",
        "food_group": "vegetable", "states": {"raw": {}},
    })
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.get("/ui/ingredients/search?q=epinard&group=meat")
    assert "No ingredients match your search." in r.text
    r2 = client.get("/ui/ingredients/search?q=epinard&group=vegetable")
    assert "spinach" in r2.text


def test_ingredients_page_prefills_query(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    html = client.get("/ui/ingredients?q=chicken").text
    assert 'value="chicken"' in html
    assert "chicken_breast" in html


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


def test_ingredient_detail_page_has_report_issue_entry_point(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    html = client.get("/ui/ingredients/chicken_breast").text
    assert "openFeedback(" in html
    assert 'id="feedback-modal"' in html


def test_submit_feedback_forwards_structured_correction(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch("app.routes.ui._post_feedback", return_value=True) as mock_post:
        r = client.post(
            "/ui/ingredients/chicken_breast/feedback",
            data={"category": "measures", "code": "reference_weight", "value": "160", "unit": "g", "comment": ""},
        )
    assert r.status_code == 200
    assert "received" in r.text.lower() or "reçu" in r.text.lower()
    payload = mock_post.call_args[0][0]
    assert payload["sourceSurface"] == "community"
    assert payload["corrections"] == [{"category": "measures", "code": "reference_weight", "value": "160", "unit": "g"}]


def test_submit_feedback_free_comment_has_no_structured_correction(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch("app.routes.ui._post_feedback", return_value=True) as mock_post:
        r = client.post(
            "/ui/ingredients/chicken_breast/feedback",
            data={"category": "other", "code": "free", "comment": "this looks wrong"},
        )
    assert r.status_code == 200
    payload = mock_post.call_args[0][0]
    assert payload["corrections"] == []
    assert payload["comment"] == "this looks wrong"


def test_submit_feedback_rejects_unknown_category_or_code(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.post(
        "/ui/ingredients/chicken_breast/feedback",
        data={"category": "measures", "code": "not_a_real_code", "value": "1"},
    )
    assert r.status_code == 400


def test_submit_feedback_rejects_blank_free_comment(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.post(
        "/ui/ingredients/chicken_breast/feedback",
        data={"category": "other", "code": "free", "comment": "  "},
    )
    assert r.status_code == 400


def test_submit_feedback_reports_upstream_failure(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch("app.routes.ui._post_feedback", return_value=False):
        r = client.post(
            "/ui/ingredients/chicken_breast/feedback",
            data={"category": "measures", "code": "reference_weight", "value": "160", "unit": "g"},
        )
    assert r.status_code == 502


def test_submit_feedback_unknown_ingredient_404s(client, fake_redis):
    r = client.post(
        "/ui/ingredients/nonexistent/feedback",
        data={"category": "measures", "code": "reference_weight", "value": "160"},
    )
    assert r.status_code == 404


def test_ingredient_detail_shows_mapping_vote_widget_with_fetched_tallies(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_mapping({
        "source": "ciqual", "source_id": "19051", "label": "Poulet",
        "canonical_ingredient_id": "chicken_breast", "confidence": 1.0,
    })
    with patch(
        "app.routes.ui._get_mapping_votes",
        return_value={"ciqual:19051:raw": {"upvotes": 4, "downvotes": 1}},
    ):
        html = client.get("/ui/ingredients/chicken_breast").text
    assert 'id="mapping-votes-ciqual-19051-raw"' in html
    assert "👍 4" in html
    assert "👎 1" in html


def test_vote_mapping_forwards_and_returns_updated_tally(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch(
        "app.routes.ui._post_mapping_vote", return_value={"upvotes": 5, "downvotes": 1},
    ) as mock_post:
        r = client.post(
            "/ui/ingredients/chicken_breast/mappings/vote",
            data={"source": "ciqual", "source_id": "19051", "cooking_method": "raw", "direction": "up"},
        )
    assert r.status_code == 200
    assert "👍 5" in r.text
    assert "👎 1" in r.text
    assert "disabled" in r.text  # locked after a successful vote
    payload = mock_post.call_args[0][0]
    assert payload == {
        "source": "ciqual", "sourceId": "19051", "cookingMethod": "raw",
        "direction": "up", "sourceSurface": "community",
    }


def test_vote_mapping_rejects_unknown_source(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.post(
        "/ui/ingredients/chicken_breast/mappings/vote",
        data={"source": "bogus", "source_id": "1", "cooking_method": "raw", "direction": "up"},
    )
    assert r.status_code == 400


def test_vote_mapping_rejects_invalid_direction(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.post(
        "/ui/ingredients/chicken_breast/mappings/vote",
        data={"source": "ciqual", "source_id": "1", "cooking_method": "raw", "direction": "sideways"},
    )
    assert r.status_code == 400


def test_vote_mapping_unknown_ingredient_404s(client, fake_redis):
    r = client.post(
        "/ui/ingredients/nonexistent/mappings/vote",
        data={"source": "ciqual", "source_id": "1", "cooking_method": "raw", "direction": "up"},
    )
    assert r.status_code == 404


def test_vote_mapping_reports_upstream_failure_and_leaves_buttons_usable(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch("app.routes.ui._post_mapping_vote", return_value=None):
        r = client.post(
            "/ui/ingredients/chicken_breast/mappings/vote",
            data={"source": "ciqual", "source_id": "19051", "cooking_method": "raw", "direction": "up"},
        )
    assert r.status_code == 502
    assert "disabled" not in r.text  # retryable, not locked out
    assert "👍 0" in r.text


def test_ingredient_detail_shows_relationship_vote_widget_with_fetched_tallies(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_relationship("chicken_breast", "grilled", {
        "raw_id": "chicken_breast", "cooking_method": "grilled", "yield_factor": 0.75, "confidence": 0.9,
    })
    with patch(
        "app.routes.ui._get_relationship_votes",
        return_value={"chicken_breast:grilled": {"upvotes": 4, "downvotes": 1}},
    ):
        html = client.get("/ui/ingredients/chicken_breast").text
    assert 'id="relationship-votes-chicken_breast-grilled"' in html
    assert "👍 4" in html
    assert "👎 1" in html


def test_ingredient_detail_has_no_vote_widget_for_theoretical_pairs_without_a_relationship(client, fake_redis, monkeypatch):
    # A training pair with no matching curated relationship (row.rel is None) must never get a
    # vote widget — it's rebuilt by ingest on every run and has no stable identity to vote on.
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    from app import db as pg_db
    monkeypatch.setattr(pg_db, "get_ingredient_training_pairs", lambda slug: [{
        "cooking_method": "boiled", "yield_f": 0.8, "is_theoretical": True,
        "cooked": {"energy_kcal": 100, "protein_g": None, "fat_g": None, "carbohydrates_g": None, "water_g": None},
    }])
    html = client.get("/ui/ingredients/chicken_breast").text
    assert 'id="relationship-votes-chicken_breast-boiled"' not in html


def test_vote_relationship_forwards_and_returns_updated_tally(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch(
        "app.routes.ui._post_relationship_vote", return_value={"upvotes": 5, "downvotes": 1},
    ) as mock_post:
        r = client.post(
            "/ui/ingredients/chicken_breast/relationships/vote",
            data={"cooking_method": "grilled", "direction": "up"},
        )
    assert r.status_code == 200
    assert "👍 5" in r.text
    assert "👎 1" in r.text
    assert "disabled" in r.text  # locked after a successful vote
    payload = mock_post.call_args[0][0]
    assert payload == {
        "ingredientId": "chicken_breast", "cookingMethod": "grilled",
        "direction": "up", "sourceSurface": "community",
    }


def test_vote_relationship_rejects_invalid_direction(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    r = client.post(
        "/ui/ingredients/chicken_breast/relationships/vote",
        data={"cooking_method": "grilled", "direction": "sideways"},
    )
    assert r.status_code == 400


def test_vote_relationship_unknown_ingredient_404s(client, fake_redis):
    r = client.post(
        "/ui/ingredients/nonexistent/relationships/vote",
        data={"cooking_method": "grilled", "direction": "up"},
    )
    assert r.status_code == 404


def test_vote_relationship_reports_upstream_failure_and_leaves_buttons_usable(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    with patch("app.routes.ui._post_relationship_vote", return_value=None):
        r = client.post(
            "/ui/ingredients/chicken_breast/relationships/vote",
            data={"cooking_method": "grilled", "direction": "up"},
        )
    assert r.status_code == 502
    assert "disabled" not in r.text  # retryable, not locked out
    assert "👍 0" in r.text


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


# ── Read-only portal: the write surface must be gone ─────────────────────────

def test_proposal_endpoints_removed(client):
    assert client.post("/api/proposals/ingredient", json={}).status_code == 404
    assert client.post("/api/proposals/mapping", json={}).status_code == 404
    assert client.post("/api/proposals/mapping/link", json={}).status_code == 404
    assert client.post("/api/proposals/relationship", json={}).status_code == 404
    assert client.put("/api/proposals/ingredient/chicken_breast", json={}).status_code == 404


def test_curation_ui_pages_removed(client):
    assert client.post("/ui/reload").status_code in (404, 405)
    assert client.get("/ui/propose").status_code == 404
    assert client.get("/ui/mappings/curate").status_code == 404
    assert client.get("/ui/sr-pairs").status_code == 404
    assert client.get("/ui/feedback").status_code == 404
    assert client.get("/ui/ingredients/chicken_breast/edit").status_code == 404


def test_nav_has_no_curation_links(client):
    html = client.get("/ui/ingredients").text
    for fragment in ("/ui/propose", "/ui/mappings/curate", "/ui/sr-pairs", "/ui/feedback", "hx-post=\"/ui/reload\""):
        assert fragment not in html


def test_admin_reload_disabled_without_token(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "reload_token", "")
    assert client.post("/admin/reload").status_code == 401
    assert client.post("/admin/reload", headers={"X-Reload-Token": ""}).status_code == 401


def test_admin_reload_with_token(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "reload_token", "s3cret")
    assert client.post("/admin/reload").status_code == 401
    r = client.post("/admin/reload", headers={"X-Reload-Token": "s3cret"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ingredient_detail_shows_read_only_enrichment(client, fake_redis):
    redis_store.set_unit_types({"glass": 200.0})
    redis_store.set_ingredient("whole_milk", {
        "id": "whole_milk", "name_en": "whole milk", "name_fr": "lait entier",
        "food_group": "dairy",
        "states": {"raw": {"portion_g": 200.0, "density_g_ml": 1.03}},
        "aliases_en": ["full-fat milk"],
        "serving_unit_types": ["glass"],
        "absorption_factors": {"fat_g": 0.5},
    })
    redis_store.set_mapping({
        "source": "ciqual", "source_id": "19051", "label": "Lait entier",
        "canonical_ingredient_id": "whole_milk", "match_method": "manual", "confidence": 1.0,
    })
    redis_store.set_relationship("whole_milk", "boiled", {
        "raw_id": "whole_milk", "cooking_method": "boiled", "yield_factor": 0.97,
    })
    html = client.get("/ui/ingredients/whole_milk").text
    assert "full-fat milk" in html          # aliases in header
    assert "At a glance" in html
    assert "Serving units" in html          # resolved serving units card
    assert "Absorption factors" in html
    assert "100 g raw → ~97 g boiled" in html   # human-readable yield
    assert "Data &amp; provenance" in html
    assert "Source mappings" in html        # provenance card
    assert "19051" in html
    assert "Propose a correction" not in html


def test_group_filter_pills_show_counts_and_hide_empty_groups(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    redis_store.set_ingredient("broccoli", {
        "id": "broccoli", "name_en": "Broccoli", "food_group": "vegetable", "states": {"raw": {}},
    })
    html = client.get("/ui/ingredients").text
    assert 'meat <span class="filter-count">1</span>' in html
    assert 'all <span class="filter-count">2</span>' in html
    assert 'data-group="fish"' not in html   # groups without ingredients are hidden


def test_ingredient_detail_shows_confidence_bars(client, fake_redis):
    redis_store.set_ingredient("rice", {
        "id": "rice", "name_en": "rice", "food_group": "cereal", "states": {"raw": {}},
    })
    redis_store.set_relationship("rice", "boiled", {
        "raw_id": "rice", "cooking_method": "boiled", "yield_factor": 2.229, "confidence": 0.9,
    })
    html = client.get("/ui/ingredients/rice").text
    assert 'class="conf"' in html
    assert "90%" in html


def test_lang_toggle_sets_cookie_and_redirects(client):
    r = client.get("/ui/lang/fr", params={"next": "/ui/ingredients?q=riz"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/ui/ingredients?q=riz"
    assert "lang=fr" in r.headers.get("set-cookie", "")


def test_lang_toggle_rejects_external_next(client):
    r = client.get("/ui/lang/en", params={"next": "https://evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/ui/ingredients"
    r2 = client.get("/ui/lang/en", params={"next": "//evil.example"}, follow_redirects=False)
    assert r2.headers["location"] == "/ui/ingredients"


def test_lang_toggle_unknown_language(client):
    assert client.get("/ui/lang/de", follow_redirects=False).status_code == 404


def test_french_browser_still_opens_in_english(client, fake_redis):
    html = client.get("/ui/ingredients", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}).text
    assert "Search by name" in html
    assert "Rechercher par nom" not in html


def test_english_is_default_without_hints(client, fake_redis):
    html = client.get("/ui/ingredients").text
    assert "Search by name" in html
    assert "Rechercher par nom" not in html


def test_french_cookie_shows_french_names_first(client, fake_redis):
    redis_store.set_ingredient("spinach", {
        "id": "spinach", "name_en": "spinach", "name_fr": "épinard",
        "food_group": "vegetable", "states": {"raw": {}},
    })
    client.cookies.set("lang", "fr")
    detail = client.get("/ui/ingredients/spinach").text
    assert "épinard</h1>" in detail          # FR name is the main title
    assert "En bref" in detail               # translated section title
    assert "légume" in detail                # translated food group badge
    client.cookies.delete("lang")


def test_ingredients_list_is_visitor_friendly(client, fake_redis):
    redis_store.set_ingredient("chicken_breast", _CHICKEN)
    html = client.get("/ui/ingredients").text
    assert "What exactly is an ingredient here?" not in html  # moved to its own /ui/about page
    assert "detail →" not in html                           # whole row is clickable instead
    assert 'href="/ui/ingredients/chicken_breast"' in html
    assert "ML service" not in html                         # no dev jargon up front


_CIQUAL_NUTRIENT_FIELDS = [
    "energy_kcal", "water_g", "proteins_g", "fat_g", "carbohydrates_g", "sugars_g", "fiber_g",
    "saturated_fat_g", "monounsaturated_fat_g", "polyunsaturated_fat_g", "cholesterol_mg",
    "calcium_mg", "iron_mg", "magnesium_mg", "sodium_mg", "potassium_mg", "phosphorus_mg", "zinc_mg",
    "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug", "vitamin_b6_mg", "vitamin_b12_ug", "niacin_mg",
]


def test_reference_browser_lists_every_mapping_regardless_of_cooking_method(client, fake_redis, monkeypatch):
    # Regression: a mapping with an uncatalogued cooking_method (e.g. "dry" for
    # uncooked rice/pasta/legumes) used to have no button in the reference
    # browser's left-hand list, even though its nutrient panel was rendered —
    # making it invisible even though the source mappings table showed it.
    from app import db as pg_db

    redis_store.set_ingredient("brown_rice", {
        "id": "brown_rice", "name_en": "brown rice", "food_group": "cereal", "states": {"raw": {}},
    })
    redis_store.set_mapping({
        "source": "ciqual", "source_id": "9102", "label": "Riz complet, cru",
        "canonical_ingredient_id": "brown_rice", "match_method": "manual", "confidence": 1.0,
        "cooking_method": "dry",
    })
    redis_store.set_mapping({
        "source": "ciqual", "source_id": "9103", "label": "Riz complet, cuit",
        "canonical_ingredient_id": "brown_rice", "match_method": "manual", "confidence": 1.0,
        "cooking_method": "boiled",
    })
    monkeypatch.setattr(pg_db, "get_ciqual_rows", lambda codes: [
        {"alim_code": int(c), "alim_nom_fr": f"Row {c}", **{f: None for f in _CIQUAL_NUTRIENT_FIELDS}}
        for c in codes
    ])
    html = client.get("/ui/ingredients/brown_rice").text
    assert 'id="btn-ciqual-0"' in html
    assert 'id="btn-ciqual-1"' in html
