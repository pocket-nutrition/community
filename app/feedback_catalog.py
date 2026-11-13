"""Guided feedback catalog for the "report an issue" flow on the ingredient page.

Mirrors pocket-nutrition-api's FeedbackController allowlist and the sandbox/iOS/Android
FeedbackCatalog: five categories of common mistakes, each listing specific errors, each
with the input its value needs. Category/error codes MUST stay in sync with the api
allowlist (FeedbackController.CODES_BY_CATEGORY) or submissions are rejected with 400.

Error labels are French-only by design, matching contract/data/strings/fr.json — the
same source every other client transcribes. The surrounding chrome (buttons, modal
copy) is translated normally via app.i18n instead.
"""
from __future__ import annotations

from pydantic import BaseModel


class FeedbackOption(BaseModel):
    code: str
    label: str


class FeedbackErrorDef(BaseModel):
    code: str
    label: str
    input_kind: str  # "number" | "number_unit" | "select" | "text"
    suffix: str | None = None
    units: list[str] = []
    options: list[FeedbackOption] = []
    placeholder: str | None = None
    # What current on-page value to show next to the field, if any. The first five
    # codes below mirror the shared deck's CurrentValueHint; name_fr/name_en/food_group
    # are this client's own addition (unambiguous single values on this page, unlike
    # iOS/Android's nutrient hints which don't apply here — see ingredient_detail.html).
    hint: str | None = None


class FeedbackCategory(BaseModel):
    code: str
    label: str
    errors: list[FeedbackErrorDef]


SERVING_UNITS = [
    FeedbackOption(code="pinch", label="pincée"),
    FeedbackOption(code="teaspoon", label="cuillère à café"),
    FeedbackOption(code="tablespoon", label="cuillère à soupe"),
    FeedbackOption(code="cup", label="tasse"),
    FeedbackOption(code="handful", label="poignée"),
    FeedbackOption(code="small_handful", label="petite poignée"),
    FeedbackOption(code="glass", label="verre"),
]

FOOD_GROUPS = [
    FeedbackOption(code="meat", label="viande"),
    FeedbackOption(code="fish", label="poisson"),
    FeedbackOption(code="shellfish", label="fruits de mer"),
    FeedbackOption(code="vegetable", label="légume"),
    FeedbackOption(code="cereal", label="céréale"),
    FeedbackOption(code="dairy", label="produit laitier"),
    FeedbackOption(code="beverage", label="boisson"),
    FeedbackOption(code="egg", label="œuf"),
    FeedbackOption(code="fat", label="matière grasse"),
    FeedbackOption(code="fruit", label="fruit"),
    FeedbackOption(code="legume", label="légumineuse"),
    FeedbackOption(code="nut_seed", label="fruit à coque / graine"),
    FeedbackOption(code="spice_herb", label="épice / herbe"),
    FeedbackOption(code="sweetener", label="édulcorant"),
    FeedbackOption(code="baked_good", label="produit de boulangerie"),
    FeedbackOption(code="sauce", label="sauce"),
    FeedbackOption(code="processed_meat", label="charcuterie"),
    FeedbackOption(code="prepared_dish", label="plat préparé"),
    FeedbackOption(code="seaweed", label="algue"),
    FeedbackOption(code="alcohol", label="alcool"),
    FeedbackOption(code="other", label="autre"),
]

COOKING_METHODS = [
    FeedbackOption(code="raw", label="cru"),
    FeedbackOption(code="boiled", label="bouilli"),
    FeedbackOption(code="steamed", label="vapeur"),
    FeedbackOption(code="grilled", label="grillé"),
    FeedbackOption(code="roasted", label="rôti"),
    FeedbackOption(code="fried", label="frit"),
    FeedbackOption(code="cooked", label="cuit (générique)"),
]

DISPLAY_UNITS = [
    FeedbackOption(code="g", label="grammes (g)"),
    FeedbackOption(code="ml", label="millilitres (ml)"),
]

SERVING_MODES = [
    FeedbackOption(code="item", label="à l'unité"),
    FeedbackOption(code="weight", label="au poids"),
    FeedbackOption(code="volume", label="au volume"),
    FeedbackOption(code="measure", label="à la mesure"),
]

RAW_COOKED = [
    FeedbackOption(code="raw", label="cru"),
    FeedbackOption(code="cooked", label="cuit"),
    FeedbackOption(code="both", label="les deux"),
]

CATEGORIES: list[FeedbackCategory] = [
    FeedbackCategory(
        code="nutrition",
        label="Valeurs nutritionnelles",
        errors=[
            FeedbackErrorDef(code="energy", label="Énergie", input_kind="number", suffix="kcal"),
            FeedbackErrorDef(code="protein", label="Protéines", input_kind="number", suffix="g"),
            FeedbackErrorDef(code="fat", label="Lipides", input_kind="number", suffix="g"),
            FeedbackErrorDef(code="carbs", label="Glucides", input_kind="number", suffix="g"),
            FeedbackErrorDef(code="fiber", label="Fibres", input_kind="number", suffix="g"),
            FeedbackErrorDef(
                code="other_nutrient", label="Autre nutriment", input_kind="text",
                placeholder="ex : vitamine C ~ 12 mg",
            ),
        ],
    ),
    FeedbackCategory(
        code="identity",
        label="Identité",
        errors=[
            FeedbackErrorDef(
                code="name_fr", label="Nom (français)", input_kind="text",
                placeholder="nom correct en français", hint="name_fr",
            ),
            FeedbackErrorDef(
                code="name_en", label="Nom (anglais)", input_kind="text",
                placeholder="correct English name", hint="name_en",
            ),
            FeedbackErrorDef(
                code="food_group", label="Groupe alimentaire", input_kind="select",
                options=FOOD_GROUPS, hint="food_group",
            ),
            FeedbackErrorDef(
                code="aliases", label="Noms alternatifs / synonymes", input_kind="text",
                placeholder="ex : poivre, poivre moulu",
            ),
            FeedbackErrorDef(
                code="wrong_ingredient", label="Mauvais ingrédient reconnu", input_kind="text",
                placeholder="le bon ingrédient serait…",
            ),
        ],
    ),
    FeedbackCategory(
        code="measures",
        label="Mesures & portions",
        errors=[
            FeedbackErrorDef(
                code="reference_weight", label="Poids de référence", input_kind="number_unit",
                units=["g", "ml"], hint="reference_weight",
            ),
            FeedbackErrorDef(
                code="serving_unit", label="Unité de mesure manquante (ex : pincée)", input_kind="select",
                options=SERVING_UNITS, hint="serving_units",
            ),
            FeedbackErrorDef(
                code="display_unit", label="Unité d'affichage", input_kind="select",
                options=DISPLAY_UNITS, hint="display_unit",
            ),
            FeedbackErrorDef(code="serving_mode", label="Mode de portion", input_kind="select", options=SERVING_MODES),
            FeedbackErrorDef(code="density", label="Densité", input_kind="number", suffix="g/ml"),
        ],
    ),
    FeedbackCategory(
        code="cooking",
        label="Cuisson",
        errors=[
            FeedbackErrorDef(code="yield", label="Rendement après cuisson", input_kind="number", suffix="%"),
            FeedbackErrorDef(
                code="cooking_method", label="Méthode de cuisson manquante", input_kind="select",
                options=COOKING_METHODS, hint="cooking_method",
            ),
            FeedbackErrorDef(
                code="raw_cooked", label="Se mange cru / cuit", input_kind="select",
                options=RAW_COOKED, hint="raw_cooked",
            ),
        ],
    ),
    FeedbackCategory(
        code="other",
        label="Autre / nouvelle information",
        errors=[
            FeedbackErrorDef(
                code="free", label="Autre remarque", input_kind="text",
                placeholder="décrivez le problème ou la nouvelle information",
            ),
        ],
    ),
]

CODES_BY_CATEGORY: dict[str, set[str]] = {cat.code: {e.code for e in cat.errors} for cat in CATEGORIES}
