from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ServingUnit(BaseModel):
    unit: str
    label_fr: str
    label_en: Optional[str] = None
    volume_ml: float
    grams: float


UNIT_LABELS_FR: dict[str, str] = {
    "pinch":         "pincée",
    "teaspoon":      "c.à.c.",
    "tablespoon":    "c.à.s.",
    "cup":           "tasse",
    "handful":       "poignée",
    "small_handful": "petite poignée",
    "glass":         "verre",
    "shot":          "dose",
    "bowl":          "bol",
    "scoop":         "mesurette",
}


class StateMetadata(BaseModel):
    portion_g: Optional[float] = None
    density_g_ml: Optional[float] = None


class Ingredient(BaseModel):
    id: str
    name_en: str
    name_fr: Optional[str] = None
    food_group: str
    states: dict[str, StateMetadata]
    notes: Optional[str] = None
    can_eat_raw: Optional[bool] = None
    can_eat_cooked: Optional[bool] = None
    typical_state: Optional[str] = None
    aliases_en: list[str] = []
    aliases_fr: list[str] = []
    serving_unit_types: list[str] = []
    serving_units: list[ServingUnit] = []
    display_unit: Optional[str] = None
    absorption_factors: dict[str, float] = {}
    serving_mode: Optional[str] = None
    unit_label_fr: Optional[str] = None
    unit_label_en: Optional[str] = None


class SourceMapping(BaseModel):
    source: str
    source_id: str
    canonical_ingredient_id: Optional[str] = None
    label: Optional[str] = None
    match_method: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    # Preparation state of the source row. Absent / "raw" = raw reference;
    # any other value groups the row under that cooking method on the UI.
    cooking_method: Optional[str] = None


class CookingRelationship(BaseModel):
    raw_id: str
    cooking_method: str
    yield_factor: float
    confidence: Optional[float] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    nutrient_retention: dict[str, float] = {}
