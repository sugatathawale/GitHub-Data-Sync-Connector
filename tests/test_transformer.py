"""Tests for data transformation."""

from __future__ import annotations

import pytest

from app.transformer import TransformError, transform_repository


def test_transform_repository_success(sample_repo_payload):
    result = transform_repository(sample_repo_payload, etag='"etag1"')

    assert result["repo_id"] == 10270250
    assert result["full_name"] == "facebook/react"
    assert result["name"] == "react"
    assert result["owner"] == "facebook"
    assert result["language"] == "JavaScript"
    assert result["stars"] == 220000
    assert result["forks"] == 45000
    assert result["open_issues"] == 1200
    assert result["html_url"] == "https://github.com/facebook/react"
    assert result["created_at"] == "2013-05-24T16:15:54Z"
    assert result["updated_at"] == "2026-03-20T10:00:00Z"
    assert result["etag"] == '"etag1"'
    assert "synced_at" in result


def test_transform_missing_required_field(sample_repo_payload):
    del sample_repo_payload["id"]

    with pytest.raises(TransformError, match="Missing required fields"):
        transform_repository(sample_repo_payload)


def test_transform_handles_null_language(sample_repo_payload):
    sample_repo_payload["language"] = None
    result = transform_repository(sample_repo_payload)
    assert result["language"] is None


def test_transform_owner_fallback_from_full_name(sample_repo_payload):
    sample_repo_payload["owner"] = {}
    result = transform_repository(sample_repo_payload)
    assert result["owner"] == "facebook"


def test_transform_invalid_root_type():
    with pytest.raises(TransformError, match="JSON object"):
        transform_repository([])  # type: ignore[arg-type]
