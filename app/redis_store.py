"""Redis store for the knowledge hot cache.

Key layout:
  knowledge:ingredient:{slug}                  → JSON string of ingredient dict
  knowledge:index:food_group:{group}           → SET of ingredient slugs by food group
  knowledge:mapping:{source}:{id}              → JSON string of full SourceMapping dict
  knowledge:index:mapping:unlinked             → SET of "{source}:{source_id}" for unlinked mappings
  knowledge:index:mapping:by_source:{source}   → SET of source_ids for a given source
  knowledge:relationship:{raw_id}:{method}     → JSON string of relationship dict
  knowledge:recipe:{id}                        → JSON string of recipe dict
  knowledge:meta:loaded_at                     → ISO timestamp of last reload
"""
from __future__ import annotations

import json
from typing import Any

import redis as _redis

from app.completeness import SOURCES, MappingTally, is_verified_mapping
from app.config import settings

_pool = _redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def _r() -> _redis.Redis:
    return _redis.Redis(connection_pool=_pool)


def flush() -> None:
    _r().flushdb()


# ── Ingredients ──────────────────────────────────────────────────────────────

def set_ingredient(slug: str, data: dict[str, Any]) -> None:
    r = _r()
    pipe = r.pipeline()
    pipe.set(f"knowledge:ingredient:{slug}", json.dumps(data))
    pipe.sadd(f"knowledge:index:food_group:{data.get('food_group', 'other')}", slug)
    pipe.execute()


def get_ingredient(slug: str) -> dict[str, Any] | None:
    raw = _r().get(f"knowledge:ingredient:{slug}")
    return json.loads(raw) if raw else None


def list_ingredient_keys() -> list[str]:
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = _r().scan(cursor, match="knowledge:ingredient:*", count=500)
        keys.extend(batch)
        if cursor == 0:
            break
    return [k.removeprefix("knowledge:ingredient:") for k in keys]


def list_slugs_by_group(food_group: str) -> list[str]:
    return sorted(_r().smembers(f"knowledge:index:food_group:{food_group}"))


def count_ingredients_by_group() -> dict[str, int]:
    """Return {food_group: ingredient count} from the food-group indexes."""
    r = _r()
    counts: dict[str, int] = {}
    cursor = 0
    while True:
        cursor, batch = r.scan(cursor, match="knowledge:index:food_group:*", count=100)
        for key in batch:
            group = key.removeprefix("knowledge:index:food_group:")
            counts[group] = r.scard(key)
        if cursor == 0:
            break
    return counts


def mget_ingredients(slugs: list[str]) -> list[dict[str, Any]]:
    if not slugs:
        return []
    values = _r().mget([f"knowledge:ingredient:{s}" for s in slugs])
    return [json.loads(v) for v in values if v is not None]


# ── Recipes ──────────────────────────────────────────────────────────────────

def set_recipe(recipe_id: str, data: dict[str, Any]) -> None:
    _r().set(f"knowledge:recipe:{recipe_id}", json.dumps(data))


def get_recipe(recipe_id: str) -> dict[str, Any] | None:
    raw = _r().get(f"knowledge:recipe:{recipe_id}")
    return json.loads(raw) if raw else None


def list_recipe_keys() -> list[str]:
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = _r().scan(cursor, match="knowledge:recipe:*", count=500)
        keys.extend(batch)
        if cursor == 0:
            break
    return [k.removeprefix("knowledge:recipe:") for k in keys]


# ── Source mappings ──────────────────────────────────────────────────────────

def set_mapping(mapping: dict[str, Any]) -> None:
    source = mapping["source"]
    source_id = mapping["source_id"]
    canonical = mapping.get("canonical_ingredient_id")
    member = f"{source}:{source_id}"
    r = _r()
    pipe = r.pipeline()
    pipe.set(f"knowledge:mapping:{source}:{source_id}", json.dumps(mapping))
    pipe.sadd(f"knowledge:index:mapping:by_source:{source}", source_id)
    if canonical:
        pipe.srem("knowledge:index:mapping:unlinked", member)
    else:
        pipe.sadd("knowledge:index:mapping:unlinked", member)
    pipe.execute()


def get_mapping(source: str, source_id: str) -> dict[str, Any] | None:
    raw = _r().get(f"knowledge:mapping:{source}:{source_id}")
    return json.loads(raw) if raw else None


def get_mapping_canonical(source: str, source_id: str) -> str | None:
    m = get_mapping(source, source_id)
    return m.get("canonical_ingredient_id") if m else None


def list_unlinked_mappings(
    source: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    members = sorted(_r().smembers("knowledge:index:mapping:unlinked"))
    if source:
        members = [m for m in members if m.startswith(f"{source}:")]
    total = len(members)
    page: list[dict[str, Any]] = []
    for member in members[offset : offset + limit]:
        src, src_id = member.split(":", 1)
        data = get_mapping(src, src_id)
        if data:
            page.append(data)
    return page, total


def list_mappings_for_ingredient(source: str, slug: str) -> list[dict[str, Any]]:
    """Return the full mapping dicts for a given source that map to slug."""
    all_ids = list(_r().smembers(f"knowledge:index:mapping:by_source:{source}"))
    if not all_ids:
        return []
    keys = [f"knowledge:mapping:{source}:{sid}" for sid in all_ids]
    values = _r().mget(keys)
    mappings = [
        data
        for v in values
        if v and (data := json.loads(v)).get("canonical_ingredient_id") == slug
    ]
    mappings.sort(key=lambda m: m["source_id"])
    return mappings


def list_source_ids_for_ingredient_by_method(
    source: str, slug: str
) -> dict[str, list[str]]:
    """Group source_ids mapping to slug by their `cooking_method`.

    Returns a dict keyed by cooking_method ("raw", "boiled", "steamed", …)
    whose values are sorted source_id lists. Mappings without an explicit
    cooking_method are bucketed under "raw" so legacy data renders correctly.
    """
    all_ids = list(_r().smembers(f"knowledge:index:mapping:by_source:{source}"))
    if not all_ids:
        return {}
    keys = [f"knowledge:mapping:{source}:{sid}" for sid in all_ids]
    values = _r().mget(keys)
    buckets: dict[str, list[str]] = {}
    for v in values:
        if not v:
            continue
        data = json.loads(v)
        if data.get("canonical_ingredient_id") != slug:
            continue
        method = data.get("cooking_method") or "raw"
        buckets.setdefault(method, []).append(data["source_id"])
    for ids in buckets.values():
        ids.sort()
    return buckets


# ── Relationships ─────────────────────────────────────────────────────────────

def set_relationship(raw_id: str, method: str, data: dict[str, Any]) -> None:
    _r().set(f"knowledge:relationship:{raw_id}:{method}", json.dumps(data))


def get_relationship(raw_id: str, method: str) -> dict[str, Any] | None:
    raw = _r().get(f"knowledge:relationship:{raw_id}:{method}")
    return json.loads(raw) if raw else None


def list_relationship_keys() -> list[tuple[str, str]]:
    keys = _r().keys("knowledge:relationship:*")
    result: list[tuple[str, str]] = []
    for k in keys:
        parts = k.removeprefix("knowledge:relationship:").rsplit(":", 1)
        if len(parts) == 2:
            result.append((parts[0], parts[1]))
    return result


def build_relationship_counts() -> dict[str, int]:
    """Count cooking relationships per raw ingredient, for the data-confidence score."""
    counts: dict[str, int] = {}
    for raw_id, _method in list_relationship_keys():
        counts[raw_id] = counts.get(raw_id, 0) + 1
    return counts


def build_mapping_tallies() -> dict[str, MappingTally]:
    """Aggregate mapping count + verified count per canonical ingredient, across all sources.

    Feeds the data-confidence score shown on the ingredient list and detail pages.
    """
    r = _r()
    raw: dict[str, dict[str, int]] = {}
    for source in SOURCES:
        source_ids = r.smembers(f"knowledge:index:mapping:by_source:{source}")
        if not source_ids:
            continue
        values = r.mget([f"knowledge:mapping:{source}:{sid}" for sid in source_ids])
        for v in values:
            if not v:
                continue
            data = json.loads(v)
            cid = data.get("canonical_ingredient_id")
            if not cid or cid == "_composite":
                continue
            entry = raw.setdefault(cid, {"total": 0, "verified": 0})
            entry["total"] += 1
            if is_verified_mapping(data):
                entry["verified"] += 1
    return {cid: MappingTally(total=v["total"], verified=v["verified"]) for cid, v in raw.items()}


# ── Unit types ────────────────────────────────────────────────────────────────

def set_unit_types(data: dict[str, float]) -> None:
    _r().set("knowledge:unit_types", json.dumps(data))


def get_unit_types() -> dict[str, float]:
    raw = _r().get("knowledge:unit_types")
    return json.loads(raw) if raw else {}


# ── Meta ──────────────────────────────────────────────────────────────────────

def set_loaded_at(ts: str) -> None:
    _r().set("knowledge:meta:loaded_at", ts)


def get_loaded_at() -> str | None:
    return _r().get("knowledge:meta:loaded_at")


# ── Dashboard stats ───────────────────────────────────────────────────────────

def get_dashboard_stats() -> dict[str, Any]:
    r = _r()
    sources = ["ciqual", "mccance", "usda", "usda_foundation", "usda_sr"]

    all_slugs = list_ingredient_keys()
    all_ingredients = mget_ingredients(all_slugs) if all_slugs else []
    ingredient_stats: dict[str, int] = {
        "total": len(all_ingredients),
        "with_name_fr": sum(1 for i in all_ingredients if i.get("name_fr")),
        "with_name_en": sum(1 for i in all_ingredients if i.get("name_en")),
    }

    unlinked_members: set[str] = r.smembers("knowledge:index:mapping:unlinked")
    mapping_stats: dict[str, dict[str, int]] = {}
    for source in sources:
        source_ids: set[str] = r.smembers(f"knowledge:index:mapping:by_source:{source}")
        total = len(source_ids)
        unlinked = sum(1 for m in unlinked_members if m.startswith(f"{source}:"))
        dismissed = 0
        if source_ids:
            keys = [f"knowledge:mapping:{source}:{sid}" for sid in source_ids]
            values = r.mget(keys)
            dismissed = sum(
                1 for v in values
                if v and json.loads(v).get("canonical_ingredient_id") == "_composite"
            )
        mapping_stats[source] = {
            "total": total,
            "linked": max(0, total - unlinked - dismissed),
            "unlinked": unlinked,
            "dismissed": dismissed,
        }

    rel_keys = list_relationship_keys()

    return {
        "ingredients": ingredient_stats,
        "mappings": mapping_stats,
        "relationships": {"total": len(rel_keys)},
        "recipes": {"total": len(list_recipe_keys())},
        "loaded_at": get_loaded_at(),
    }
