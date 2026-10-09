"""Synchronization orchestration: extract → transform → load."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.database import Database, DatabaseError
from app.github_client import (
    AuthError,
    FetchResult,
    GitHubClient,
    GitHubClientError,
    InvalidRepoNameError,
    InvalidResponseError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from app.transformer import TransformError, transform_repository

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result for a single repository sync attempt."""

    full_name: str
    status: str  # success | unchanged | failed
    message: str
    repo_id: int | None = None
    action: str | None = None  # inserted | updated | skipped


@dataclass
class SyncSummary:
    """Aggregate outcome for one sync batch."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    unchanged: int = 0
    duration_seconds: float = 0.0
    results: list[SyncResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "unchanged": self.unchanged,
            "duration_seconds": round(self.duration_seconds, 3),
            "results": [
                {
                    "full_name": item.full_name,
                    "status": item.status,
                    "message": item.message,
                    "repo_id": item.repo_id,
                    "action": item.action,
                }
                for item in self.results
            ],
        }


# In-memory last-run status for the optional FastAPI demo endpoint.
_last_sync_summary: SyncSummary | None = None


def get_last_sync_status() -> dict[str, Any] | None:
    if _last_sync_summary is None:
        return None
    return _last_sync_summary.to_dict()


class SyncService:
    """Coordinates GitHub fetch, transformation, and database UPSERT."""

    def __init__(
        self,
        client: GitHubClient | None = None,
        database: Database | None = None,
    ) -> None:
        self.client = client or GitHubClient()
        self.database = database or Database()

    def sync_repository(self, full_name: str) -> SyncResult:
        """Fetch, validate, transform, and UPSERT a single repository."""
        logger.info("Sync started for %s", full_name)
        try:
            etag = self.database.get_etag(full_name)
            fetch_result: FetchResult = self.client.fetch_repository(
                full_name, etag=etag
            )

            if fetch_result.status == "not_modified":
                message = "Source unchanged (HTTP 304); skipped write"
                logger.info("Sync unchanged for %s", full_name)
                return SyncResult(
                    full_name=full_name,
                    status="unchanged",
                    message=message,
                    action="skipped",
                )

            raw = fetch_result.data
            if raw is None:
                raise InvalidResponseError("Empty response body")

            transformed = transform_repository(raw, etag=fetch_result.etag)
            action = self.database.upsert_repository(transformed)

            message = f"Repository {action} successfully"
            logger.info("Sync completed for %s (%s)", full_name, action)
            return SyncResult(
                full_name=full_name,
                status="success",
                message=message,
                repo_id=transformed["repo_id"],
                action=action,
            )

        except (
            NotFoundError,
            AuthError,
            RateLimitError,
            ServerError,
            NetworkError,
            InvalidResponseError,
            InvalidRepoNameError,
            TransformError,
            DatabaseError,
            GitHubClientError,
        ) as exc:
            # Never include tokens or Authorization headers in messages.
            logger.error("Sync failed for %s: %s", full_name, exc)
            return SyncResult(
                full_name=full_name,
                status="failed",
                message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - unexpected safety net
            logger.exception("Unexpected sync error for %s", full_name)
            return SyncResult(
                full_name=full_name,
                status="failed",
                message=f"Unexpected error: {exc}",
            )

    def sync_repositories(self, full_names: list[str]) -> SyncSummary:
        """Synchronize multiple repositories and return a summary."""
        global _last_sync_summary

        started = time.perf_counter()
        logger.info("Batch sync started for %s repositories", len(full_names))

        summary = SyncSummary(total=len(full_names))
        for name in full_names:
            result = self.sync_repository(name)
            summary.results.append(result)
            if result.status == "success":
                summary.succeeded += 1
            elif result.status == "unchanged":
                summary.unchanged += 1
            else:
                summary.failed += 1

        summary.duration_seconds = time.perf_counter() - started
        _last_sync_summary = summary

        logger.info(
            "Sync completion summary: total=%s succeeded=%s failed=%s "
            "unchanged=%s duration=%.3fs",
            summary.total,
            summary.succeeded,
            summary.failed,
            summary.unchanged,
            summary.duration_seconds,
        )
        return summary
