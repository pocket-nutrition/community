"""HTMX/Jinja2 UI routes — public read-only portal."""
from __future__ import annotations

import asyncio
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db as pg_db
from app import feedback_catalog
from app import redis_store
from app.completeness import SOURCES as _SOURCES_WITH_METHOD_GROUPING
from app.completeness import Completeness, MappingTally, build_completeness, is_verified_mapping
from app.config import settings
from app.i18n import LANG_COOKIE, SUPPORTED, i18n_context
from app.routes.ingredients import _resolve_serving_units
from app.schemas import CookingRelationship, Ingredient
from app.search import search_ingredients

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates", context_processors=[i18n_context])

# The Knowledge Editor install guide lives in the website's documentation, so there is one
# version of it; /ui/knowledge-editor stays as a redirect for older links.
KNOWLEDGE_EDITOR_GUIDE_URL = "https://website.pocketnutrition.org/docs/contribute/knowledge-editor"
templates.env.globals["knowledge_editor_guide_url"] = KNOWLEDGE_EDITOR_GUIDE_URL

_ONE_YEAR = 365 * 24 * 3600


@router.get("/lang/{lang_code}", include_in_schema=False)
def set_lang(lang_code: str, next: str = "/ui/ingredients") -> RedirectResponse:
    if lang_code not in SUPPORTED:
        raise HTTPException(status_code=404, detail="Unsupported language")
    # Only allow same-site relative redirects.
    target = next if next.startswith("/") and not next.startswith("//") else "/ui/ingredients"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(LANG_COOKIE, lang_code, max_age=_ONE_YEAR, samesite="lax")
    return response

PAGE_SIZE = 50


@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request) -> HTMLResponse:
    stats = redis_store.get_dashboard_stats()
    training_pairs = pg_db.get_training_pairs_stats()
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "training_pairs": training_pairs,
    })


@router.get("/dashboard", include_in_schema=False)
def dashboard_redirect() -> RedirectResponse:
    return RedirectResponse("/ui/stats", status_code=301)


@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("about.html", {"request": request})


@router.get("/knowledge-editor", include_in_schema=False)
def knowledge_editor_page() -> RedirectResponse:
    return RedirectResponse(KNOWLEDGE_EDITOR_GUIDE_URL, status_code=301)


_SORT_KEYS = ("name", "confidence_asc", "confidence_desc")
DEFAULT_SORT = "confidence_desc"


@router.get("/ingredients", response_class=HTMLResponse)
def ingredients_page(
    request: Request, q: str = "", group: str = "", page: int = 1, sort: str = DEFAULT_SORT,
) -> HTMLResponse:
    sort = sort if sort in _SORT_KEYS else DEFAULT_SORT
    slugs = _get_slugs(group or None)
    ingredients, completeness, pagination = _paginate(slugs, page, q=q or None, sort=sort)
    group_counts = redis_store.count_ingredients_by_group()
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "ingredients": ingredients,
        "completeness": completeness,
        "q": q,
        "group": group,
        "sort": sort,
        "group_counts": group_counts,
        "total_all": sum(group_counts.values()),
        **pagination,
    })


@router.get("/ingredients/search", response_class=HTMLResponse)
def ingredients_search(
    request: Request, q: str = "", group: str = "", page: int = 1, sort: str = DEFAULT_SORT,
) -> HTMLResponse:
    sort = sort if sort in _SORT_KEYS else DEFAULT_SORT
    slugs = _get_slugs(group or None)
    ingredients, completeness, pagination = _paginate(slugs, page, q=q or None, sort=sort)
    response = templates.TemplateResponse("partials/ingredient_rows.html", {
        "request": request,
        "ingredients": ingredients,
        "completeness": completeness,
        "q": q,
        "group": group,
        "sort": sort,
        **pagination,
    })
    # Keep the browser URL on the full page (not this partial) so searches
    # are shareable and survive a reload.
    params = urlencode({
        k: v for k, v in (("q", q), ("group", group), ("sort", sort if sort != DEFAULT_SORT else ""), ("page", page if page > 1 else ""))
        if v
    })
    response.headers["HX-Push-Url"] = f"/ui/ingredients?{params}" if params else "/ui/ingredients"
    return response


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


def _methods_for_source(source: str, slug: str) -> dict[str, str]:
    """Return {source_id: cooking_method} for all mappings of source → slug."""
    buckets = redis_store.list_source_ids_for_ingredient_by_method(source, slug)
    return {sid: method for method, ids in buckets.items() for sid in ids}


@router.get("/ingredients/{slug}", response_class=HTMLResponse)
async def ingredient_detail(request: Request, slug: str) -> HTMLResponse:
    data = redis_store.get_ingredient(slug)
    if data is None:
        return HTMLResponse("<p>Ingredient not found.</p>", status_code=404)
    ingredient = Ingredient(**data)
    serving_units = _resolve_serving_units(data, redis_store.get_unit_types())
    relationships = [
        CookingRelationship(**redis_store.get_relationship(r_id, method))
        for r_id, method in redis_store.list_relationship_keys()
        if r_id == slug
    ]
    source_mappings = {
        source: redis_store.list_mappings_for_ingredient(source, slug)
        for source in _SOURCES_WITH_METHOD_GROUPING
    }
    ciqual_ids = [m["source_id"] for m in source_mappings["ciqual"]]
    mccance_ids = [m["source_id"] for m in source_mappings["mccance"]]
    usda_ids = [m["source_id"] for m in source_mappings["usda"]]
    usda_foundation_ids = [m["source_id"] for m in source_mappings["usda_foundation"]]
    usda_sr_ids = [m["source_id"] for m in source_mappings["usda_sr"]]
    ref_methods = {
        source: _methods_for_source(source, slug)
        for source in _SOURCES_WITH_METHOD_GROUPING
    }
    all_mappings = [m for maps in source_mappings.values() for m in maps]
    mapping_keys = [_mapping_vote_key(m) for m in all_mappings]
    votes_by_key = await _get_mapping_votes(mapping_keys)
    for m, key in zip(all_mappings, mapping_keys):
        m["votes"] = votes_by_key.get(key, {"upvotes": 0, "downvotes": 0})
    mapping_votes = {key: m["votes"] for m, key in zip(all_mappings, mapping_keys)}
    relationship_keys = [_relationship_vote_key(rel) for rel in relationships]
    relationship_votes_by_key = await _get_relationship_votes(relationship_keys)
    relationship_votes = {
        key: relationship_votes_by_key.get(key, {"upvotes": 0, "downvotes": 0})
        for key in relationship_keys
    }
    tally = MappingTally(
        total=len(all_mappings),
        verified=sum(1 for m in all_mappings if is_verified_mapping(m)),
    )
    completeness = build_completeness(data, tally, len(relationships))
    return templates.TemplateResponse(
        "ingredient_detail.html",
        {
            "request": request,
            "ingredient": ingredient,
            "completeness": completeness,
            "serving_units": serving_units,
            "relationships": relationships,
            "source_mappings": source_mappings,
            "ciqual_rows": pg_db.get_ciqual_rows(ciqual_ids),
            "mccance_rows": pg_db.get_mccance_rows(mccance_ids),
            "usda_rows": pg_db.get_usda_rows(usda_ids),
            "usda_foundation_rows": pg_db.get_usda_foundation_rows(usda_foundation_ids),
            "usda_sr_rows": pg_db.get_usda_sr_rows(usda_sr_ids),
            "usda_cooking_yield_rows": pg_db.get_usda_cooking_yield_rows(ingredient.name_en),
            "ref_methods": ref_methods,
            "mapping_votes": mapping_votes,
            "relationship_votes": relationship_votes,
            "training_pairs": pg_db.get_ingredient_training_pairs(slug),
            "feedback_categories": feedback_catalog.CATEGORIES,
        },
    )


async def _post_feedback(payload: dict) -> bool:
    """Forward a feedback report to pocket-nutrition-api, which owns the feedback_report
    table. Community never writes it directly — see FeedbackReport.kt's doc comment."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.api_url}/feedback", json=payload, timeout=5.0)
        return resp.status_code == 201
    except httpx.HTTPError:
        return False


@router.post("/ingredients/{slug}/feedback", response_class=HTMLResponse)
async def submit_feedback(
    request: Request,
    slug: str,
    category: str = Form(...),
    code: str = Form(...),
    value: str = Form(""),
    unit: str = Form(""),
    comment: str = Form(""),
) -> HTMLResponse:
    t = i18n_context(request)["t"]
    lang = i18n_context(request)["lang"]

    valid_codes = feedback_catalog.CODES_BY_CATEGORY.get(category)
    if valid_codes is None or code not in valid_codes:
        return templates.TemplateResponse(
            "partials/feedback_result.html", {"request": request, "ok": False, "message": t["feedback_error_invalid"]},
            status_code=400,
        )

    data = redis_store.get_ingredient(slug)
    if data is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient = Ingredient(**data)
    reported_name = (ingredient.name_fr if lang == "fr" else ingredient.name_en) or ingredient.name_en

    value = value.strip()
    comment = comment.strip()
    is_free_comment = category == "other" and code == "free"
    if is_free_comment:
        if not comment:
            return templates.TemplateResponse(
                "partials/feedback_result.html", {"request": request, "ok": False, "message": t["feedback_error_empty"]},
                status_code=400,
            )
        corrections = []
    else:
        if not value:
            return templates.TemplateResponse(
                "partials/feedback_result.html", {"request": request, "ok": False, "message": t["feedback_error_empty"]},
                status_code=400,
            )
        corrections = [{"category": category, "code": code, "value": value, "unit": unit.strip() or None}]

    payload = {
        "name": reported_name,
        "corrections": corrections,
        "comment": comment or None,
        "sourceSurface": "community",
    }
    ok = await _post_feedback(payload)
    return templates.TemplateResponse(
        "partials/feedback_result.html",
        {"request": request, "ok": ok, "message": t["feedback_success"] if ok else t["feedback_error_server"]},
        status_code=200 if ok else 502,
    )


_VALID_VOTE_DIRECTIONS = {"up", "down"}


def _mapping_vote_key(mapping: dict) -> str:
    return f"{mapping['source']}:{mapping['source_id']}:{mapping.get('cooking_method') or 'raw'}"


async def _get_mapping_votes(keys: list[str]) -> dict[str, dict]:
    """Batch-fetch current confidence tallies for the mapping associations shown on this
    page, from pocket-nutrition-api's mapping_vote_tally table. Falls back to all-zero
    tallies if the api is unreachable — a vote-count hiccup must never break the page."""
    if not keys:
        return {}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.api_url}/mappings/votes",
                params=[("key", k) for k in keys],
                timeout=5.0,
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return {}


async def _post_mapping_vote(payload: dict) -> dict | None:
    """Forward a confidence vote to pocket-nutrition-api, which owns the mapping_vote_tally
    table. Community never writes it directly — same side-channel pattern as _post_feedback."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.api_url}/mappings/vote", json=payload, timeout=5.0)
        if resp.status_code != 201:
            return None
        return resp.json()
    except httpx.HTTPError:
        return None


@router.post("/ingredients/{slug}/mappings/vote", response_class=HTMLResponse)
async def vote_mapping(
    request: Request,
    slug: str,
    source: str = Form(...),
    source_id: str = Form(...),
    cooking_method: str = Form(...),
    direction: str = Form(...),
    dom_suffix: str = Form(""),
) -> HTMLResponse:
    if source not in _SOURCES_WITH_METHOD_GROUPING or direction not in _VALID_VOTE_DIRECTIONS:
        return HTMLResponse("Invalid vote", status_code=400)

    data = redis_store.get_ingredient(slug)
    if data is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    payload = {
        "source": source,
        "sourceId": source_id,
        "cookingMethod": cooking_method,
        "direction": direction,
        "sourceSurface": "community",
    }
    tally = await _post_mapping_vote(payload)
    return templates.TemplateResponse(
        "partials/mapping_vote.html",
        {
            "request": request,
            "ingredient_id": slug,
            "source": source,
            "source_id": source_id,
            "cooking_method": cooking_method,
            "votes": tally or {"upvotes": 0, "downvotes": 0},
            "ok": tally is not None,
            "dom_suffix": dom_suffix,
        },
        status_code=200 if tally is not None else 502,
    )


def _relationship_vote_key(rel: CookingRelationship) -> str:
    return f"{rel.raw_id}:{rel.cooking_method}"


async def _get_relationship_votes(keys: list[str]) -> dict[str, dict]:
    """Batch-fetch current confidence tallies for the cooking relationships shown on this
    page, from pocket-nutrition-api's relationship_vote_tally table. Falls back to all-zero
    tallies if the api is unreachable — a vote-count hiccup must never break the page."""
    if not keys:
        return {}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.api_url}/relationships/votes",
                params=[("key", k) for k in keys],
                timeout=5.0,
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return {}


async def _post_relationship_vote(payload: dict) -> dict | None:
    """Forward a confidence vote to pocket-nutrition-api, which owns the
    relationship_vote_tally table. Community never writes it directly — same side-channel
    pattern as _post_feedback / _post_mapping_vote."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.api_url}/relationships/vote", json=payload, timeout=5.0)
        if resp.status_code != 201:
            return None
        return resp.json()
    except httpx.HTTPError:
        return None


@router.post("/ingredients/{slug}/relationships/vote", response_class=HTMLResponse)
async def vote_relationship(
    request: Request,
    slug: str,
    cooking_method: str = Form(...),
    direction: str = Form(...),
    dom_suffix: str = Form(""),
) -> HTMLResponse:
    if direction not in _VALID_VOTE_DIRECTIONS:
        return HTMLResponse("Invalid vote", status_code=400)

    data = redis_store.get_ingredient(slug)
    if data is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    payload = {
        "ingredientId": slug,
        "cookingMethod": cooking_method,
        "direction": direction,
        "sourceSurface": "community",
    }
    tally = await _post_relationship_vote(payload)
    return templates.TemplateResponse(
        "partials/relationship_vote.html",
        {
            "request": request,
            "ingredient_id": slug,
            "cooking_method": cooking_method,
            "votes": tally or {"upvotes": 0, "downvotes": 0},
            "ok": tally is not None,
            "dom_suffix": dom_suffix,
        },
        status_code=200 if tally is not None else 502,
    )


def _get_slugs(food_group: str | None) -> list[str]:
    if food_group:
        return redis_store.list_slugs_by_group(food_group)
    return sorted(redis_store.list_ingredient_keys())


def _paginate(
    slugs: list[str],
    page: int,
    q: str | None,
    sort: str = "name",
) -> tuple[list[Ingredient], dict[str, Completeness], dict]:
    tallies = redis_store.build_mapping_tallies()
    rel_counts = redis_store.build_relationship_counts()

    def score(data: dict) -> Completeness:
        tally = tallies.get(data["id"], MappingTally())
        return build_completeness(data, tally, rel_counts.get(data["id"], 0))

    if q or sort != "name":
        all_data = redis_store.mget_ingredients(slugs)
        if q:
            all_data = search_ingredients(all_data, q)
        if sort != "name":
            all_data.sort(key=lambda d: score(d).overall, reverse=(sort == "confidence_desc"))
        total = len(all_data)
        offset = (page - 1) * PAGE_SIZE
        page_data = all_data[offset:offset + PAGE_SIZE]
    else:
        total = len(slugs)
        offset = (page - 1) * PAGE_SIZE
        page_data = redis_store.mget_ingredients(slugs[offset:offset + PAGE_SIZE])

    ingredients = [Ingredient(**d) for d in page_data]
    completeness = {d["id"]: score(d) for d in page_data}

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return ingredients, completeness, {
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "page_start": offset + 1 if total > 0 else 0,
        "page_end": min(offset + PAGE_SIZE, total),
    }
