from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app import redis_store
from app.schemas import Ingredient, ServingUnit, UNIT_LABELS_FR

router = APIRouter(prefix="/api/ingredients", tags=["ingredients"])


def _resolve_serving_units(data: dict, unit_volumes: dict[str, float]) -> list[ServingUnit]:
    units: list[ServingUnit] = []

    # whole-item unit for countable ingredients
    if data.get("serving_mode") == "item" and data.get("unit_label_fr"):
        portion_g = next(
            (s.get("portion_g") for s in (data.get("states") or {}).values() if s.get("portion_g")),
            None,
        )
        if portion_g:
            units.append(ServingUnit(
                unit="item",
                label_fr=data["unit_label_fr"],
                label_en=data.get("unit_label_en"),
                volume_ml=0.0,
                grams=portion_g,
            ))

    # volumetric units (require density)
    density = next(
        (v for s in (data.get("states") or {}).values() if (v := s.get("density_g_ml"))),
        None,
    )
    if density:
        units.extend(
            ServingUnit(
                unit=u,
                label_fr=UNIT_LABELS_FR.get(u, u),
                volume_ml=unit_volumes[u],
                grams=round(unit_volumes[u] * density, 2),
            )
            for u in data.get("serving_unit_types") or []
            if u in unit_volumes
        )

    return units


@router.get("", response_model=list[Ingredient])
def list_ingredients(food_group: str | None = None) -> list[Ingredient]:
    slugs = redis_store.list_ingredient_keys()
    unit_volumes = redis_store.get_unit_types()
    result: list[Ingredient] = []
    for slug in sorted(slugs):
        data = redis_store.get_ingredient(slug)
        if data is None:
            continue
        if food_group and data.get("food_group") != food_group:
            continue
        result.append(Ingredient(**data, serving_units=_resolve_serving_units(data, unit_volumes)))
    return result


@router.get("/{slug}", response_model=dict)
def get_ingredient(slug: str) -> dict:
    data = redis_store.get_ingredient(slug)
    if data is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    unit_volumes = redis_store.get_unit_types()
    serving_units = [u.model_dump() for u in _resolve_serving_units(data, unit_volumes)]

    relationships = []
    for raw_id, method in redis_store.list_relationship_keys():
        if raw_id == slug:
            rel = redis_store.get_relationship(raw_id, method)
            if rel:
                relationships.append(rel)

    return {**data, "serving_units": serving_units, "cooking_relationships": relationships}


@router.get("/resolve/{source}/{source_id}")
def resolve_mapping(source: str, source_id: str) -> dict:
    mapping = redis_store.get_mapping(source, source_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="No mapping found")
    canonical = mapping.get("canonical_ingredient_id")
    if canonical is None:
        raise HTTPException(status_code=409, detail="Mapping exists but is not yet linked to a canonical ingredient")
    return {"canonical_ingredient_id": canonical}
