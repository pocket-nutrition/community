"""Read-only PostgreSQL access for community UI enrichment."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine = None
_SessionLocal = None


def _get_factory() -> sessionmaker | None:
    global _engine, _SessionLocal
    if not settings.database_url:
        return None
    if _SessionLocal is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session | None, None, None]:
    factory = _get_factory()
    if factory is None:
        yield None
        return
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_ciqual_rows(alim_codes: list[str]) -> list[dict[str, Any]]:
    if not alim_codes:
        return []
    with get_session() as session:
        if session is None:
            return []
        result = session.execute(
            text("SELECT * FROM ciqual_foods WHERE alim_code = ANY(:codes) ORDER BY alim_code"),
            {"codes": [int(c) for c in alim_codes]},
        )
        return [dict(row._mapping) for row in result]


def get_mccance_rows(food_codes: list[str]) -> list[dict[str, Any]]:
    if not food_codes:
        return []
    with get_session() as session:
        if session is None:
            return []
        result = session.execute(
            text("SELECT * FROM mccance_foods WHERE food_code = ANY(:codes) ORDER BY food_code"),
            {"codes": food_codes},
        )
        return [dict(row._mapping) for row in result]


def get_usda_rows(fdc_ids: list[str]) -> list[dict[str, Any]]:
    if not fdc_ids:
        return []
    with get_session() as session:
        if session is None:
            return []
        result = session.execute(
            text("SELECT * FROM usda_foods WHERE fdc_id = ANY(:ids) ORDER BY fdc_id"),
            {"ids": [int(i) for i in fdc_ids]},
        )
        return [dict(row._mapping) for row in result]


def get_usda_foundation_rows(fdc_ids: list[str]) -> list[dict[str, Any]]:
    if not fdc_ids:
        return []
    with get_session() as session:
        if session is None:
            return []
        result = session.execute(
            text("SELECT * FROM usda_foundation_foods WHERE fdc_id = ANY(:ids) ORDER BY fdc_id"),
            {"ids": [int(i) for i in fdc_ids]},
        )
        return [dict(row._mapping) for row in result]


def get_usda_sr_rows(fdc_ids: list[str]) -> list[dict[str, Any]]:
    if not fdc_ids:
        return []
    with get_session() as session:
        if session is None:
            return []
        result = session.execute(
            text("SELECT * FROM usda_sr_foods WHERE fdc_id = ANY(:ids) ORDER BY fdc_id"),
            {"ids": [int(i) for i in fdc_ids]},
        )
        return [dict(row._mapping) for row in result]


_COOKED_DISPLAY_COLS = ["energy_kcal", "protein_g", "fat_g", "carbohydrates_g", "water_g"]


def get_ingredient_training_pairs(slug: str) -> list[dict[str, Any]]:
    """Return training pairs for a given ingredient slug, with key cooked nutrients pre-extracted."""
    with get_session() as session:
        if session is None:
            return []
        try:
            import json as _json
            rows = session.execute(
                text(
                    "SELECT cooking_method, source, is_theoretical, yield_f, cooked_profile"
                    " FROM v2_training_pairs"
                    " WHERE food_name = :slug"
                    " ORDER BY cooking_method"
                ),
                {"slug": slug},
            ).mappings().all()
            result = []
            for row in rows:
                cooked_raw = _json.loads(row["cooked_profile"]) if row["cooked_profile"] else {}
                result.append({
                    "cooking_method": row["cooking_method"],
                    "source": row["source"],
                    "is_theoretical": row["is_theoretical"],
                    "yield_f": row["yield_f"],
                    "cooked": {col: cooked_raw.get(col) for col in _COOKED_DISPLAY_COLS},
                })
            return result
        except Exception:
            return []


def get_training_pairs_stats() -> dict[str, int] | None:
    """Return {total, known, theoretical} counts from v2_training_pairs, or None if unavailable."""
    with get_session() as session:
        if session is None:
            return None
        try:
            row = session.execute(text(
                "SELECT"
                "  COUNT(*) AS total,"
                "  COUNT(*) FILTER (WHERE NOT is_theoretical) AS known,"
                "  COUNT(*) FILTER (WHERE is_theoretical) AS theoretical"
                " FROM v2_training_pairs"
            )).mappings().first()
            return {"total": row["total"], "known": row["known"], "theoretical": row["theoretical"]} if row else None
        except Exception:
            return None


def get_usda_cooking_yield_rows(name_en: str) -> list[dict[str, Any]]:
    """Return usda_cooking_yields rows whose food_description contains the ingredient name."""
    if not name_en:
        return []
    with get_session() as session:
        if session is None:
            return []
        result = session.execute(
            text(
                "SELECT * FROM usda_cooking_yields"
                " WHERE food_description ILIKE :pattern"
                " ORDER BY food_description, cooking_description"
            ),
            {"pattern": f"%{name_en}%"},
        )
        return [dict(row._mapping) for row in result]
