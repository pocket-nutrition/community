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


@pytest.fixture(autouse=True)
def mock_mapping_votes():
    # Ingredient detail pages batch-fetch vote tallies from pocket-nutrition-api; default to
    # all-zero here so tests never make a real network call. Tests exercising the vote feature
    # itself override this with their own patch.
    with patch("app.routes.ui._get_mapping_votes", return_value={}):
        yield


@pytest.fixture(autouse=True)
def mock_relationship_votes():
    # Same rationale as mock_mapping_votes, for the cooking-relationship vote tallies.
    with patch("app.routes.ui._get_relationship_votes", return_value={}):
        yield


@pytest.fixture
def client(fake_redis, mock_github_client):
    with TestClient(app) as c:
        yield c
