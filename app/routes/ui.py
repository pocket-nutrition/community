"""HTMX/Jinja2 UI routes."""
from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db as pg_db
from app import redis_store
from app.config import settings
from app.schemas import CookingRelationship, Ingredient

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates")

PAGE_SIZE = 50


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    stats = redis_store.get_dashboard_stats()
    training_pairs = pg_db.get_training_pairs_stats()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "training_pairs": training_pairs,
    })


@router.get("/ingredients", response_class=HTMLResponse)
def ingredients_page(request: Request, food_group: str | None = None, page: int = 1) -> HTMLResponse:
    slugs = _get_slugs(food_group)
    ingredients, pagination = _paginate(slugs, page, q=None, food_group=food_group)
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "ingredients": ingredients,
        "food_group": food_group,
        **pagination,
    })


@router.get("/ingredients/autocomplete", response_class=HTMLResponse)
def ingredients_autocomplete(canonical_ingredient_id: str = "") -> HTMLResponse:
    q = canonical_ingredient_id.strip().lower()
    if len(q) < 2:
        return HTMLResponse("")
    slugs = sorted(redis_store.list_ingredient_keys())
    matches = [s for s in slugs if q in s][:15]
    return HTMLResponse("".join(f'<option value="{s}">' for s in matches))


@router.get("/ingredients/search", response_class=HTMLResponse)
def ingredients_search(request: Request, q: str = "", group: str = "", page: int = 1) -> HTMLResponse:
    slugs = _get_slugs(group or None)
    ingredients, pagination = _paginate(slugs, page, q=q or None, food_group=group or None)
    return templates.TemplateResponse("partials/ingredient_rows.html", {
        "request": request,
        "ingredients": ingredients,
        "q": q,
        "group": group,
        **pagination,
    })


@router.get("/ingredients/{slug}/predictions", response_class=HTMLResponse)
async def ingredient_predictions(request: Request, slug: str) -> HTMLResponse:
    data = redis_store.get_ingredient(slug)
    if data is None:
        return HTMLResponse("<p>Ingredient not found.</p>", status_code=404)
    ingredient = Ingredient(**data)
    relationships = [
        CookingRelationship(**redis_store.get_relationship(r_id, method))
        for r_id, method in redis_store.list_relationship_keys()
        if r_id == slug
    ]
    methods: list[str] = [rel.cooking_method for rel in relationships]
    if ingredient.can_eat_raw is True and "raw" not in methods:
        methods = ["raw"] + methods

    async def fetch_method(client: httpx.AsyncClient, method: str) -> tuple[str, dict | str]:
        payload = [{
            "name": ingredient.name_en,
            "ingredientId": ingredient.id,
            "quantity": 100.0,
            "unit": "g",
            "cookingMethod": method,
            "measuredState": "raw",
        }]
        try:
            resp = await client.post(
                f"{settings.api_url}/nutrition",
                json=payload,
                timeout=5.0,
            )
            resp.raise_for_status()
            items = resp.json()
            return method, items[0] if items else {}
        except Exception as exc:
            return method, str(exc)

    results: dict[str, dict | str] = {}
    if methods:
        async with httpx.AsyncClient() as client:
            pairs = await asyncio.gather(*(fetch_method(client, m) for m in methods))
        results = dict(pairs)

    return templates.TemplateResponse(
        "partials/nutrition_predictions.html",
        {"request": request, "ingredient": ingredient, "results": results, "methods": methods},
    )


_SOURCES_WITH_METHOD_GROUPING: tuple[str, ...] = (
    "ciqual",
    "mccance",
    "usda",
    "usda_foundation",
    "usda_sr",
)


def _methods_for_source(source: str, slug: str) -> dict[str, str]:
    """Return {source_id: cooking_method} for all mappings of source → slug."""
    buckets = redis_store.list_source_ids_for_ingredient_by_method(source, slug)
    return {sid: method for method, ids in buckets.items() for sid in ids}


@router.get("/ingredients/{slug}", response_class=HTMLResponse)
def ingredient_detail(request: Request, slug: str) -> HTMLResponse:
    data = redis_store.get_ingredient(slug)
    if data is None:
        return HTMLResponse("<p>Ingredient not found.</p>", status_code=404)
    ingredient = Ingredient(**data)
    relationships = [
        CookingRelationship(**redis_store.get_relationship(r_id, method))
        for r_id, method in redis_store.list_relationship_keys()
        if r_id == slug
    ]
    ciqual_ids = redis_store.list_source_ids_for_ingredient("ciqual", slug)
    mccance_ids = redis_store.list_source_ids_for_ingredient("mccance", slug)
    usda_ids = redis_store.list_source_ids_for_ingredient("usda", slug)
    usda_foundation_ids = redis_store.list_source_ids_for_ingredient("usda_foundation", slug)
    usda_sr_ids = redis_store.list_source_ids_for_ingredient("usda_sr", slug)
    ref_methods = {
        source: _methods_for_source(source, slug)
        for source in _SOURCES_WITH_METHOD_GROUPING
    }
    return templates.TemplateResponse(
        "ingredient_detail.html",
        {
            "request": request,
            "ingredient": ingredient,
            "relationships": relationships,
            "ciqual_rows": pg_db.get_ciqual_rows(ciqual_ids),
            "mccance_rows": pg_db.get_mccance_rows(mccance_ids),
            "usda_rows": pg_db.get_usda_rows(usda_ids),
            "usda_foundation_rows": pg_db.get_usda_foundation_rows(usda_foundation_ids),
            "usda_sr_rows": pg_db.get_usda_sr_rows(usda_sr_ids),
            "usda_cooking_yield_rows": pg_db.get_usda_cooking_yield_rows(ingredient.name_en),
            "ref_methods": ref_methods,
            "training_pairs": pg_db.get_ingredient_training_pairs(slug),
        },
    )


@router.get("/relationships", response_class=HTMLResponse)
def relationships_page(request: Request) -> HTMLResponse:
    rels = [
        CookingRelationship(**redis_store.get_relationship(r_id, method))
        for r_id, method in sorted(redis_store.list_relationship_keys())
    ]
    return templates.TemplateResponse("relationships.html", {"request": request, "relationships": rels})


@router.post("/reload", response_class=HTMLResponse)
def reload_cache(request: Request) -> HTMLResponse:
    from app.loader import reload
    counts = reload()
    unlinked = counts.get("unlinked_mappings", 0)
    unlinked_suffix = f", {unlinked} unlinked" if unlinked else ""
    msg = f"Loaded {counts['ingredients']} ingredients, {counts['mappings']} mappings{unlinked_suffix}, {counts['relationships']} relationships."
    return HTMLResponse(f'<span id="cache-msg" style="color:#27ae60;font-size:0.85rem;">{msg}</span>')


@router.get("/sr-pairs", response_class=HTMLResponse)
def sr_pairs_page(request: Request, page: int = 1) -> HTMLResponse:
    offset = (page - 1) * PAGE_SIZE
    pairs, total = redis_store.list_sr_pairs(offset=offset, limit=PAGE_SIZE)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("sr_pairs.html", {
        "request": request,
        "pairs": pairs,
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "page_start": offset + 1 if total else 0,
        "page_end": min(offset + PAGE_SIZE, total),
    })


@router.get("/feedback", response_class=HTMLResponse)
def feedback_page(request: Request, ingredient: str | None = None) -> HTMLResponse:
    """Read-only moderation view of anonymous user feedback collected by pocket-nutrition-api.

    This page never modifies the knowledge base — the team applies accepted corrections
    separately, via the knowledge-editor review tool.
    """
    summary = pg_db.get_feedback_summary()
    reports = pg_db.get_feedback_reports(ingredient_id=ingredient)
    total = sum(row["report_count"] for row in summary)
    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "summary": summary,
        "reports": reports,
        "selected": ingredient,
        "total": total,
    })


def _get_slugs(food_group: str | None) -> list[str]:
    if food_group:
        return redis_store.list_slugs_by_group(food_group)
    return sorted(redis_store.list_ingredient_keys())


def _paginate(
    slugs: list[str],
    page: int,
    q: str | None,
    food_group: str | None,
) -> tuple[list[Ingredient], dict]:
    if q:
        q_lower = q.lower()
        all_data = redis_store.mget_ingredients(slugs)
        filtered = [
            Ingredient(**d) for d in all_data
            if q_lower in d["id"]
            or q_lower in d["name_en"].lower()
            or (d.get("name_fr") and q_lower in d["name_fr"].lower())
        ]
        total = len(filtered)
        offset = (page - 1) * PAGE_SIZE
        ingredients = filtered[offset:offset + PAGE_SIZE]
    else:
        total = len(slugs)
        offset = (page - 1) * PAGE_SIZE
        ingredients = [
            Ingredient(**d)
            for d in redis_store.mget_ingredients(slugs[offset:offset + PAGE_SIZE])
        ]

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return ingredients, {
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "page_start": offset + 1 if total > 0 else 0,
        "page_end": min(offset + PAGE_SIZE, total),
    }
