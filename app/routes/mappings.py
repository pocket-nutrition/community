"""Read-only mappings API — lists source mappings not yet linked to a canonical ingredient."""
from __future__ import annotations

from fastapi import APIRouter
from app import redis_store

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


@router.get("/unlinked")
def list_unlinked_mappings(
    source: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    items, total = redis_store.list_unlinked_mappings(source=source, offset=offset, limit=limit)
    return {"items": items, "total": total, "offset": offset, "limit": limit}
