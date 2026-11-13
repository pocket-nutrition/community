"""Clone pocket-nutrition-knowledge from GitHub and populate Redis.

Called at service startup and by POST /admin/reload.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import yaml

from app.github_client import github
from app import redis_store

log = logging.getLogger(__name__)


def _parse_yaml(content: str) -> dict | None:
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as exc:
        log.warning("YAML parse error: %s", exc)
        return None


def _aggregate_relationships(entries: list[dict]) -> dict:
    """Merge multiple measurements for the same (raw_id, method) into one Redis entry.

    When several YAML files share the same raw_id + cooking_method (e.g. USDA
    sub-cut variants), we average their yield_factors and keep the highest
    confidence. Single-entry groups are returned unchanged.
    """
    if len(entries) == 1:
        return entries[0]

    avg_yield = round(sum(e["yield_factor"] for e in entries) / len(entries), 4)
    best_conf = max(e.get("confidence", 0.0) for e in entries)
    base = max(entries, key=lambda e: e.get("confidence", 0.0))
    return {
        **base,
        "yield_factor": avg_yield,
        "confidence": best_conf,
        "variant_count": len(entries),
    }


def reload() -> dict[str, int]:
    log.info("Reloading knowledge cache from GitHub (archive download)")

    counts = {"ingredients": 0, "mappings": 0, "unlinked_mappings": 0, "relationships": 0, "recipes": 0, "errors": 0, "unit_types": 0}

    redis_store.flush()

    # Relationships are staged and aggregated before writing so that multiple
    # variant files for the same (raw_id, method) are merged into one Redis key.
    rel_staging: dict[tuple[str, str], list[dict]] = {}

    for path, content in github.iter_yaml_files("main"):
        data = _parse_yaml(content)
        if data is None:
            counts["errors"] += 1
            continue

        if path == "serving_unit_types.yaml":
            redis_store.set_unit_types(data)
            counts["unit_types"] += 1

        elif path.startswith("ingredients/"):
            slug = data.get("id")
            if slug:
                redis_store.set_ingredient(slug, data)
                counts["ingredients"] += 1

        elif path.startswith("source_mappings/"):
            src = data.get("source")
            src_id = data.get("source_id")
            if src and src_id:
                redis_store.set_mapping({
                    "source": src,
                    "source_id": str(src_id),
                    "canonical_ingredient_id": data.get("canonical_ingredient_id"),
                    "label": data.get("label"),
                    "match_method": data.get("match_method"),
                    "confidence": data.get("confidence"),
                    "notes": data.get("notes"),
                    "cooking_method": data.get("cooking_method") or "raw",
                })
                counts["mappings"] += 1
                if not data.get("canonical_ingredient_id"):
                    counts["unlinked_mappings"] += 1

        elif path.startswith("recipes/"):
            recipe_id = data.get("id")
            if recipe_id:
                redis_store.set_recipe(recipe_id, data)
                counts["recipes"] += 1

        elif path.startswith("cooking_relationships/"):
            raw_id = data.get("raw_id")
            method = data.get("cooking_method")
            if raw_id and method:
                rel_staging.setdefault((raw_id, method), []).append(data)

    for (raw_id, method), entries in rel_staging.items():
        aggregated = _aggregate_relationships(entries)
        redis_store.set_relationship(raw_id, method, aggregated)
        counts["relationships"] += 1

    redis_store.set_loaded_at(datetime.now(UTC).isoformat())
    log.info("Cache reload complete: %s", counts)
    return counts
