"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app.database import Database


SAMPLE_REPO_PAYLOAD = {
    "id": 10270250,
    "name": "react",
    "full_name": "facebook/react",
    "html_url": "https://github.com/facebook/react",
    "language": "JavaScript",
    "stargazers_count": 220000,
    "forks_count": 45000,
    "open_issues_count": 1200,
    "created_at": "2013-05-24T16:15:54Z",
    "updated_at": "2026-03-20T10:00:00Z",
    "owner": {"login": "facebook"},
}


@pytest.fixture
def sample_repo_payload() -> dict:
    return dict(SAMPLE_REPO_PAYLOAD)


@pytest.fixture
def temp_db(tmp_path) -> Database:
    db_path = tmp_path / "test_github_sync.db"
    return Database(db_path=db_path)
