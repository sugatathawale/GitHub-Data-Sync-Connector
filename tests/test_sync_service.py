"""Tests for the synchronization engine."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.github_client import FetchResult, NotFoundError
from app.sync_service import SyncService


def test_successful_synchronization(temp_db, sample_repo_payload):
    client = MagicMock()
    client.fetch_repository.return_value = FetchResult(
        status="ok", data=sample_repo_payload, etag='"etag"'
    )
    service = SyncService(client=client, database=temp_db)

    result = service.sync_repository("facebook/react")

    assert result.status == "success"
    assert result.action == "inserted"
    assert result.repo_id == 10270250
    assert temp_db.get_repository(10270250) is not None


def test_failed_synchronization_404(temp_db):
    client = MagicMock()
    client.fetch_repository.side_effect = NotFoundError("Repository not found")
    service = SyncService(client=client, database=temp_db)

    result = service.sync_repository("missing/repo")

    assert result.status == "failed"
    assert "not found" in result.message.lower()
    assert temp_db.count_repositories() == 0


def test_unchanged_synchronization_skips_write(temp_db, sample_repo_payload):
    from app.transformer import transform_repository

    temp_db.upsert_repository(
        transform_repository(sample_repo_payload, etag='"etag"')
    )
    client = MagicMock()
    client.fetch_repository.return_value = FetchResult(
        status="not_modified", etag='"etag"'
    )
    service = SyncService(client=client, database=temp_db)

    result = service.sync_repository("facebook/react")

    assert result.status == "unchanged"
    assert result.action == "skipped"
    client.fetch_repository.assert_called_once()


def test_sync_repositories_summary(temp_db, sample_repo_payload):
    client = MagicMock()
    client.fetch_repository.side_effect = [
        FetchResult(status="ok", data=sample_repo_payload, etag='"e1"'),
        NotFoundError("Repository not found"),
    ]
    service = SyncService(client=client, database=temp_db)

    summary = service.sync_repositories(["facebook/react", "missing/repo"])

    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert summary.duration_seconds >= 0
