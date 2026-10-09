"""Tests for SQLite storage and UPSERT behavior."""

from __future__ import annotations

from app.transformer import transform_repository


def test_insert_repository(temp_db, sample_repo_payload):
    repo = transform_repository(sample_repo_payload, etag='"e1"')
    action = temp_db.upsert_repository(repo)

    assert action == "inserted"
    stored = temp_db.get_repository(repo["repo_id"])
    assert stored is not None
    assert stored["full_name"] == "facebook/react"
    assert stored["stars"] == 220000
    assert stored["etag"] == '"e1"'


def test_upsert_updates_existing_row(temp_db, sample_repo_payload):
    repo = transform_repository(sample_repo_payload, etag='"e1"')
    temp_db.upsert_repository(repo)

    sample_repo_payload["stargazers_count"] = 221000
    sample_repo_payload["updated_at"] = "2026-03-21T10:00:00Z"
    updated = transform_repository(sample_repo_payload, etag='"e2"')
    action = temp_db.upsert_repository(updated)

    assert action == "updated"
    stored = temp_db.get_repository(repo["repo_id"])
    assert stored["stars"] == 221000
    assert stored["updated_at"] == "2026-03-21T10:00:00Z"
    assert stored["etag"] == '"e2"'


def test_duplicate_prevention(temp_db, sample_repo_payload):
    repo = transform_repository(sample_repo_payload)
    temp_db.upsert_repository(repo)
    temp_db.upsert_repository(repo)

    assert temp_db.count_repositories() == 1


def test_get_etag(temp_db, sample_repo_payload):
    repo = transform_repository(sample_repo_payload, etag='"abc"')
    temp_db.upsert_repository(repo)

    assert temp_db.get_etag("facebook/react") == '"abc"'
    assert temp_db.get_etag("missing/repo") is None


def test_list_repositories(temp_db, sample_repo_payload):
    temp_db.upsert_repository(transform_repository(sample_repo_payload))
    rows = temp_db.list_repositories()
    assert len(rows) == 1
    assert rows[0]["name"] == "react"
