from __future__ import annotations

from fastapi import APIRouter
from app import redis_store
from app.schemas import CookingRelationship

router = APIRouter(prefix="/api/relationships", tags=["relationships"])


@router.get("", response_model=list[CookingRelationship])
def list_relationships(raw_id: str | None = None, cooking_method: str | None = None) -> list[CookingRelationship]:
    result: list[CookingRelationship] = []
    for r_id, method in sorted(redis_store.list_relationship_keys()):
        if raw_id and r_id != raw_id:
            continue
        if cooking_method and method != cooking_method:
            continue
        data = redis_store.get_relationship(r_id, method)
        if data:
            result.append(CookingRelationship(**data))
    return result
