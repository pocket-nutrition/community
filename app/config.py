from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Override via the GITHUB_REPO env var (see .env.example) to point at your own
    # fork of the pocket-nutrition/knowledge repository.
    github_repo: str = "pocket-nutrition/knowledge"
    github_token: str = ""
    redis_url: str = "redis://redis:6379/2"
    reload_token: str = "changeme"
    database_url: str | None = None
    api_url: str = "http://openfood-api:8080"

    class Config:
        env_file = ".env"


settings = Settings()
