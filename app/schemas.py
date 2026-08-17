from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


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


class ProposalMappingCreate(BaseModel):
    source: str = Field(..., pattern="^(ciqual|mccance|usda|usda_foundation|usda_sr)$")
    source_id: str = Field(..., min_length=1)
    label: Optional[str] = Field(None, max_length=256)
    canonical_ingredient_id: Optional[str] = Field(None, pattern="^[a-z0-9_]{1,128}$")
    match_method: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = None
    reason: Optional[str] = None


class ProposalMappingLink(BaseModel):
    source: str = Field(..., pattern="^(ciqual|mccance|usda|usda_foundation|usda_sr)$")
    source_id: str = Field(..., min_length=1)
    canonical_ingredient_id: str = Field(..., pattern="^[a-z0-9_]{1,128}$")
    match_method: str = "manual"
    confidence: float = Field(1.0, ge=0, le=1)
    notes: Optional[str] = None
    reason: Optional[str] = None


class ProposalRelationship(BaseModel):
    raw_id: str = Field(..., pattern="^[a-z0-9_]{1,128}$")
    cooking_method: str = Field(..., pattern="^(boiled|steamed|grilled|roasted|fried)$")
    yield_factor: float = Field(..., ge=0.1, le=5.0)
    confidence: float = Field(0.9, ge=0, le=1)
    source: str = "manual"
    notes: Optional[str] = None
    nutrient_retention: Optional[dict[str, float]] = None
    reason: Optional[str] = None


class ProposalIngredient(BaseModel):
    id: str = Field(..., pattern="^[a-z0-9_]{1,128}$")
    name_en: str = Field(..., min_length=1)
    name_fr: Optional[str] = None
    food_group: str = Field(..., pattern="^(meat|fish|shellfish|vegetable|cereal|dairy|beverage|egg|fat|other|fruit|legume|nut_seed|spice_herb|sweetener|baked_good|sauce|processed_meat|prepared_dish|seaweed|alcohol)$")
    # `state` identifies the preparation state for portion_g / density_g_ml in the form.
    # to_yaml_dict() folds these three flat fields into the nested `states` structure.
    state: str = Field("raw", pattern="^(raw|cooked|processed)$")
    notes: Optional[str] = None
    reason: Optional[str] = None
    portion_g: Optional[float] = Field(None, ge=1, le=5000)
    density_g_ml: Optional[float] = Field(None, ge=0.1, le=20)
    can_eat_raw: Optional[bool] = None
    can_eat_cooked: Optional[bool] = None
    typical_state: Optional[str] = Field(None, pattern="^(raw|cooked|processed|boiled|steamed|grilled|roasted|fried)$")

    @field_validator("typical_state", "can_eat_raw", "can_eat_cooked", "portion_g", "density_g_ml", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return None if v == "" else v

    def to_yaml_dict(self) -> dict:
        """Return a dict ready to be serialized as YAML using the new `states` schema."""
        state_entry: dict = {}
        if self.portion_g is not None:
            state_entry["portion_g"] = self.portion_g
        if self.density_g_ml is not None:
            state_entry["density_g_ml"] = self.density_g_ml

        data: dict = {
            "id": self.id,
            "name_en": self.name_en,
            "food_group": self.food_group,
            "states": {self.state: state_entry},
        }
        if self.name_fr:
            data["name_fr"] = self.name_fr
        if self.notes:
            data["notes"] = self.notes
        if self.typical_state:
            data["typical_state"] = self.typical_state
        if self.can_eat_raw is not None:
            data["can_eat_raw"] = self.can_eat_raw
        if self.can_eat_cooked is not None:
            data["can_eat_cooked"] = self.can_eat_cooked
        return data
