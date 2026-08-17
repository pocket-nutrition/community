"""GitHub API client — downloads the knowledge repo archive and reads YAML files from it."""
from __future__ import annotations

import io
import tarfile
from typing import Generator

import httpx

from app.config import settings

API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self) -> None:
        self._repo = settings.github_repo
        self._headers = {"Content-Type": "application/json"}
        if settings.github_token:
            self._headers["Authorization"] = f"token {settings.github_token}"

    def iter_yaml_files(self, branch: str = "main") -> Generator[tuple[str, str], None, None]:
        """Download the repo archive and yield (path, yaml_content) for every .yaml file."""
        archive_url = f"{API_BASE}/repos/{self._repo}/tarball/{branch}"
        with httpx.stream("GET", archive_url, headers=self._headers, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            data = b"".join(r.iter_bytes())

        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                # Strip the leading repo-branch prefix directory GitHub adds to tarballs
                # (e.g. "pocket-nutrition-knowledge-abc1234/")
                parts = member.name.split("/", 1)
                if len(parts) < 2:
                    continue
                rel_path = parts[1]
                if not rel_path.endswith(".yaml"):
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                yield rel_path, f.read().decode()


github = GitHubClient()
