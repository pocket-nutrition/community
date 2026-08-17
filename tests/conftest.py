from __future__ import annotations

import fakeredis
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.fixture(autouse=True)
def fake_redis():
    fake = fakeredis.FakeRedis(decode_responses=True)
    with patch("app.redis_store._r", new=lambda: fake):
        yield fake


@pytest.fixture(autouse=True)
def mock_github_client(monkeypatch):
    from app.github_client import github
    monkeypatch.setattr(github, "iter_yaml_files", lambda branch: iter([]))


@pytest.fixture
def client(fake_redis, mock_github_client):
    with TestClient(app) as c:
        yield c
