from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.loader import reload
from app import redis_store

router = APIRouter(prefix="/admin", tags=["admin"])

_api_key_header = APIKeyHeader(name="X-Reload-Token", auto_error=False)


def _verify_token(token: str | None = Security(_api_key_header)) -> None:
    # An unset RELOAD_TOKEN disables the endpoint entirely.
    if not settings.reload_token or token != settings.reload_token:
        raise HTTPException(status_code=401, detail="Invalid reload token")


@router.post("/reload", dependencies=[Depends(_verify_token)])
def trigger_reload() -> dict:
    counts = reload()
    return {"status": "ok", "counts": counts, "loaded_at": redis_store.get_loaded_at()}


@router.get("/status")
def status() -> dict:
    return {
        "loaded_at": redis_store.get_loaded_at(),
        "ingredient_count": len(redis_store.list_ingredient_keys()),
        "relationship_count": len(redis_store.list_relationship_keys()),
    }
