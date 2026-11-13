from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Override via the GITHUB_REPO env var (see .env.example) to point at your own
    # fork of the pocket-nutrition/knowledge repository.
    github_repo: str = "pocket-nutrition/knowledge"
    # Optional: a public repository can be read without a token. Only needed to raise the
    # GitHub API rate limit.
    github_token: str = ""
    redis_url: str = "redis://redis:6379/2"
    # No default on purpose: when unset, POST /admin/reload is disabled.
    reload_token: str = ""
    database_url: str | None = None
    api_url: str = "https://api.pocketnutrition.org"

    class Config:
        env_file = ".env"


settings = Settings()
