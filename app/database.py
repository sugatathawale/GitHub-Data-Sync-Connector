"""SQLite persistence for synchronized GitHub repositories."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from app.config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS repositories (
    repo_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    language TEXT,
    stars INTEGER NOT NULL DEFAULT 0,
    forks INTEGER NOT NULL DEFAULT 0,
    open_issues INTEGER NOT NULL DEFAULT 0,
    html_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    etag TEXT
);
"""

UPSERT_SQL = """
INSERT INTO repositories (
    repo_id, full_name, name, owner, language,
    stars, forks, open_issues, html_url,
    created_at, updated_at, synced_at, etag
) VALUES (
    :repo_id, :full_name, :name, :owner, :language,
    :stars, :forks, :open_issues, :html_url,
    :created_at, :updated_at, :synced_at, :etag
)
ON CONFLICT(repo_id) DO UPDATE SET
    full_name = excluded.full_name,
    name = excluded.name,
    owner = excluded.owner,
    language = excluded.language,
    stars = excluded.stars,
    forks = excluded.forks,
    open_issues = excluded.open_issues,
    html_url = excluded.html_url,
    created_at = excluded.created_at,
    updated_at = excluded.updated_at,
    synced_at = excluded.synced_at,
    etag = excluded.etag;
"""


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class Database:
    """Simple SQLite helper with parameterized queries and UPSERT support."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DATABASE_PATH
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        """Create the repositories table if it does not exist."""
        try:
            with self._connect() as connection:
                connection.execute(SCHEMA_SQL)
                connection.commit()
            logger.debug("Database initialized at %s", self.db_path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to initialize database: {exc}") from exc

    def upsert_repository(self, repo: dict[str, Any]) -> str:
        """
        Insert or update a repository row.

        Returns 'inserted' or 'updated'.
        """
        try:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT repo_id FROM repositories WHERE repo_id = ?",
                    (repo["repo_id"],),
                ).fetchone()
                connection.execute(UPSERT_SQL, repo)
                connection.commit()
            action = "updated" if existing else "inserted"
            logger.info(
                "Database %s for repo_id=%s (%s)",
                action,
                repo["repo_id"],
                repo.get("full_name"),
            )
            return action
        except sqlite3.Error as exc:
            logger.error("Database error during upsert: %s", exc)
            raise DatabaseError(f"Failed to upsert repository: {exc}") from exc

    def get_repository(self, repo_id: int) -> dict[str, Any] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM repositories WHERE repo_id = ?",
                    (repo_id,),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to fetch repository: {exc}") from exc

    def get_repository_by_full_name(self, full_name: str) -> dict[str, Any] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM repositories WHERE full_name = ?",
                    (full_name,),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to fetch repository by name: {exc}") from exc

    def list_repositories(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM repositories ORDER BY full_name"
                ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to list repositories: {exc}") from exc

    def get_etag(self, full_name: str) -> str | None:
        """Return the stored ETag for conditional requests, if any."""
        record = self.get_repository_by_full_name(full_name)
        if not record:
            return None
        return record.get("etag")

    def count_repositories(self) -> int:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM repositories"
                ).fetchone()
            return int(row["count"]) if row else 0
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to count repositories: {exc}") from exc
