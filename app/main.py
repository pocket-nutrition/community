"""pocket-nutrition-community FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.loader import reload
from app.routes import admin, ingredients, mappings, relationships, ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("Loading knowledge cache from GitHub…")
    try:
        reload()
    except Exception as exc:
        log.warning("Initial reload failed (GitHub may not be reachable): %s", exc)
    yield


app = FastAPI(title="Pocket Nutrition Community", lifespan=_lifespan)

app.include_router(ingredients.router)
app.include_router(mappings.router)
app.include_router(relationships.router)
app.include_router(admin.router)
app.include_router(ui.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/ui/dashboard")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
