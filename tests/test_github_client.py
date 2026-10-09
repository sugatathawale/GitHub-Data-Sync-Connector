"""Tests for the GitHub API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.github_client import (
    GitHubClient,
    InvalidRepoNameError,
    InvalidResponseError,
    NetworkError,
    NotFoundError,
)


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    headers: dict | None = None,
    raise_json: bool = False,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    if raise_json:
        response.json.side_effect = ValueError("bad json")
    else:
        response.json.return_value = json_data or {}
    return response


def test_fetch_repository_success(sample_repo_payload):
    client = GitHubClient(session=MagicMock(), max_retries=0)
    client.session.get.return_value = _mock_response(
        200, sample_repo_payload, headers={"ETag": '"abc123"'}
    )

    result = client.fetch_repository("facebook/react")

    assert result.status == "ok"
    assert result.data["full_name"] == "facebook/react"
    assert result.etag == '"abc123"'
    client.session.get.assert_called_once()


def test_fetch_repository_timeout():
    client = GitHubClient(session=MagicMock(), max_retries=0)
    client.session.get.side_effect = requests.Timeout("timed out")

    with pytest.raises(NetworkError, match="timed out"):
        client.fetch_repository("facebook/react")


def test_fetch_repository_404():
    client = GitHubClient(session=MagicMock(), max_retries=0)
    client.session.get.return_value = _mock_response(404)

    with pytest.raises(NotFoundError, match="not found"):
        client.fetch_repository("missing/repo")


def test_fetch_repository_invalid_json():
    client = GitHubClient(session=MagicMock(), max_retries=0)
    client.session.get.return_value = _mock_response(200, raise_json=True)

    with pytest.raises(InvalidResponseError, match="Invalid JSON"):
        client.fetch_repository("facebook/react")


def test_fetch_repository_invalid_name():
    client = GitHubClient(session=MagicMock(), max_retries=0)

    with pytest.raises(InvalidRepoNameError):
        client.fetch_repository("not-a-valid-name")


def test_fetch_repository_not_modified():
    client = GitHubClient(session=MagicMock(), max_retries=0)
    client.session.get.return_value = _mock_response(304)

    result = client.fetch_repository("facebook/react", etag='"abc123"')

    assert result.status == "not_modified"
    assert result.data is None


@patch("app.github_client.time.sleep", return_value=None)
def test_retry_on_500_then_success(mock_sleep, sample_repo_payload):
    client = GitHubClient(session=MagicMock(), max_retries=2)
    client.session.get.side_effect = [
        _mock_response(500),
        _mock_response(200, sample_repo_payload, headers={"ETag": '"v1"'}),
    ]

    result = client.fetch_repository("facebook/react")

    assert result.status == "ok"
    assert client.session.get.call_count == 2
    mock_sleep.assert_called()
