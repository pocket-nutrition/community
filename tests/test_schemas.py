from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ProposalIngredient, ProposalMappingCreate, ProposalRelationship


def test_proposal_ingredient_valid():
    p = ProposalIngredient(id="chicken_breast", name_en="Chicken breast", food_group="meat")
    assert p.id == "chicken_breast"
    assert p.state == "raw"
    yaml_dict = p.to_yaml_dict()
    assert "states" in yaml_dict
    assert "raw" in yaml_dict["states"]


def test_proposal_ingredient_invalid_id_uppercase():
    with pytest.raises(ValidationError):
        ProposalIngredient(id="Chicken_Breast", name_en="Chicken breast", food_group="meat")


def test_proposal_ingredient_invalid_food_group():
    with pytest.raises(ValidationError):
        ProposalIngredient(id="chicken_breast", name_en="Chicken breast", food_group="poultry")


def test_proposal_mapping_valid_sources():
    for source in ("ciqual", "mccance", "usda"):
        p = ProposalMappingCreate(source=source, source_id="123")
        assert p.source == source


def test_proposal_mapping_invalid_source():
    with pytest.raises(ValidationError):
        ProposalMappingCreate(source="unknown_db", source_id="123")


def test_proposal_relationship_yield_too_low():
    with pytest.raises(ValidationError):
        ProposalRelationship(raw_id="chicken_breast", cooking_method="grilled", yield_factor=0.05)


def test_proposal_relationship_yield_too_high():
    with pytest.raises(ValidationError):
        ProposalRelationship(raw_id="chicken_breast", cooking_method="grilled", yield_factor=6.0)


def test_proposal_relationship_invalid_cooking_method():
    with pytest.raises(ValidationError):
        ProposalRelationship(raw_id="chicken_breast", cooking_method="microwaved", yield_factor=0.8)
