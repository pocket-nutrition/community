# Contributing to Pocket Nutrition Community

Thanks for your interest in improving the Community service. This document
covers local development setup, running the test suite, and the PR workflow.

## Development Setup

```bash
git clone https://github.com/pocket-nutrition/community.git
cd community

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-test.txt

cp .env.example .env
# edit .env — see "Pointing at your own knowledge fork" below
```

Run the app locally:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app needs a reachable Redis instance (`REDIS_URL` in `.env`). `DATABASE_URL`
is optional — leave it unset to skip PostgreSQL-backed enrichment. The GitHub
knowledge repo is only fetched at startup and on `POST /admin/reload`; if it's
unreachable, startup logs a warning and continues (see `app/main.py`).

## Pointing at Your Own Knowledge Fork

By default the service reads its ingredient catalogue directly from the real
public `pocket-nutrition/knowledge` repository on GitHub — no token needed for
read access. To develop against your own fork instead:

1. Fork `pocket-nutrition/knowledge` on GitHub.
2. Set the following in your `.env`:

   ```bash
   GITHUB_REPO=your-username/knowledge
   GITHUB_TOKEN=<optional-token>
   ```

3. Restart the app (or call `POST /admin/reload` with the `X-Reload-Token`
   header set to your `RELOAD_TOKEN`) to materialize the fork's YAML files
   into Redis.

For most test-writing and unit-development work you do **not** need network
access at all — the test suite (see below) mocks the GitHub client and
uses `fakeredis`, so `pytest` runs fully offline.

## Running Tests

```bash
pytest tests/
```

Tests use `fakeredis` (no real Redis needed) and mock `app.github_client.github`
(no real GitHub/network access needed) via the fixtures in `tests/conftest.py`.
Add new tests under `tests/` alongside the existing `test_api.py`,
`test_redis_store.py`, and `test_schemas.py`.

## Code Style

- Python 3.12, type-annotated function signatures throughout `app/`.
- Keep route handlers thin; push logic into `app/loader.py`,
  `app/redis_store.py`, `app/github_client.py`, or `app/db.py` as appropriate.
- Match the existing FastAPI router-per-domain layout in `app/routes/` when
  adding new endpoints.

## Branch & PR Workflow

1. Fork the repository and create a feature branch off `main`:
   `git checkout -b feat/short-description`.
2. Make focused commits with clear messages (`feat:`, `fix:`, `docs:`,
   `test:`, `refactor:`, `chore:` prefixes are welcome but not required).
3. Ensure `pytest tests/` passes before opening a PR.
4. Open a PR against `main` describing what changed and why. Link any related
   issue.
5. Keep PRs focused — prefer several small PRs over one large one.

## Reporting Issues

Please use the issue templates under `.github/ISSUE_TEMPLATE/` when filing a
bug report or feature request. Include:

- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Environment details (Python version, OS, whether Redis/Postgres are
  local or remote)

## CI and releases

- Every pull request runs `.github/workflows/ci.yml`. The `ci-success` check must be green before a pull
  request can be merged, the branch must be up to date with `main`, and pull requests are squash-merged
  so history stays linear.
- If you contribute from a fork, the workflow waits for a maintainer to approve it. It runs with a
  read-only token and no secrets.
- Every commit merged to `main` is released automatically with a CalVer version, `vYYYY.M.N`: the year, the
  month, then a counter that restarts at 1 each month (for example `v2026.11.1`). You never pick a version
  number or edit a changelog; release notes are generated from the merged pull requests.
- A release publishes the container image `ghcr.io/pocket-nutrition/community`.
