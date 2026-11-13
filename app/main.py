"""pocket-nutrition-community FastAPI application — public read-only portal."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.loader import reload
from app.routes import admin, ingredients, mappings, relationships, ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not settings.reload_token:
        log.warning("RELOAD_TOKEN is not set — POST /admin/reload is disabled.")
    log.info("Loading knowledge cache from GitHub…")
    try:
        reload()
    except Exception as exc:
        log.warning("Initial reload failed (GitHub may not be reachable): %s", exc)
    yield


app = FastAPI(title="Pocket Nutrition — Food Dataset", lifespan=_lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(ingredients.router)
app.include_router(mappings.router)
app.include_router(relationships.router)
app.include_router(admin.router)
app.include_router(ui.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/ui/ingredients")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
