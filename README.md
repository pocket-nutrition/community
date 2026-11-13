# Pocket Nutrition — Community Service

A read-only FastAPI app for browsing the `pocket-nutrition/knowledge` ingredient
catalogue: ingredients, cooking relationships, source mappings, and user
feedback reports.

## What it does

- **Loads the knowledge base.** At startup (and on demand via `POST /admin/reload`),
  it downloads a tarball of the configured GitHub knowledge repository branch,
  parses every `*.yaml` file, and writes ingredients, source mappings, cooking
  relationships, recipes, and serving-unit types into Redis.
- **Serves a browsing UI** in French and English (cookie, then `Accept-Language`):
  ingredient list with search, ingredient detail pages with a data-confidence
  indicator and live nutrition predictions, dataset statistics, a glossary/About
  page, and a Knowledge Editor page. Visitors can report a data issue on an
  ingredient and vote on the confidence of a source mapping or a cooking
  relationship; votes and reports are forwarded to the nutrition API
  (`API_URL`), nothing is stored here.
- **Exposes a read-only REST API** for ingredient, mapping, and
  cooking-relationship data, for other services to consume.
- **Optionally enriches pages from PostgreSQL.** If `DATABASE_URL` is set, it
  reads raw source rows (Ciqual, McCance, USDA) and training pairs to display
  alongside each ingredient. The app works fine without a database configured.

This service only reads from GitHub and writes to Redis — it never writes to
PostgreSQL and never edits the knowledge base itself.

## Stack

- Python 3.12, FastAPI, Jinja2 + HTMX templates
- Redis (via `redis-py`) as the materialized knowledge cache
- SQLAlchemy + psycopg2 for optional read-only PostgreSQL enrichment
- PyYAML for parsing the knowledge repository
- httpx for calling the GitHub API and an optional downstream nutrition API

## Setup

```bash
cp .env.example .env
# defaults to the real public pocket-nutrition/knowledge repo — override GITHUB_REPO
# to point at your own fork instead, and set a strong RELOAD_TOKEN.

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The app expects a running Redis instance at `REDIS_URL` (see `.env.example`
for the default). `DATABASE_URL` is optional — leave it unset to disable the
PostgreSQL-backed enrichment features.

Once running:
- UI: `http://localhost:8000/ui/ingredients`
- Health check: `GET /health`
- API docs (OpenAPI/Swagger): `http://localhost:8000/docs`

### Docker

```bash
docker build -t pocket-nutrition-community .
docker run --rm -p 8000:8000 --env-file .env pocket-nutrition-community
```

The `Dockerfile` installs `requirements.txt` and runs
`uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Configuration

All configuration is environment-variable driven (see `app/config.py` and
`.env.example`):

| Variable | Purpose |
|---|---|
| `GITHUB_REPO` | `owner/repo` path of the knowledge repository (defaults to the real public `pocket-nutrition/knowledge`) |
| `GITHUB_TOKEN` | Optional GitHub token, only needed to raise the API rate limit for a public repo |
| `REDIS_URL` | Redis connection string for the materialized knowledge cache |
| `DATABASE_URL` | Optional PostgreSQL connection string for read-only enrichment |
| `RELOAD_TOKEN` | Bearer token required on `POST /admin/reload` — set this to a strong random value in production |
| `API_URL` | Base URL of the nutrition API used for predictions, feedback and votes on ingredient pages (defaults to `https://api.pocketnutrition.org`) |

## Tests

```bash
pip install -r requirements.txt -r requirements-test.txt
pytest tests/ -v
```

Tests use `fakeredis` and mock the GitHub client, so no external services are
required.

## License

AGPL-3.0 — see `LICENSE`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
