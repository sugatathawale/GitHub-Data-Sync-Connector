"""Optional FastAPI application exposing sync and repository endpoints.

Note: This local interview demo has no authentication. A production
deployment would require appropriate access controls (API keys, OAuth, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, status

from app.config import DATABASE_PATH, setup_logging
from app.database import Database, DatabaseError
from app.schemas import (
    HealthResponse,
    RepositoryOut,
    SyncRequest,
    SyncResponse,
)
from app.sync_service import SyncService, get_last_sync_status

setup_logging()

app = FastAPI(
    title="GitHub Data Sync Connector",
    description=(
        "Mini data integration demo: sync GitHub repository metadata into SQLite. "
        "No authentication is configured — suitable for local demos only."
    ),
    version="1.0.0",
)

_database = Database()
_sync_service = SyncService(database=_database)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        count = _database.count_repositories()
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return HealthResponse(
        status="ok",
        database_path=str(DATABASE_PATH),
        repository_count=count,
    )


@app.post("/sync", response_model=SyncResponse)
def sync_repositories(payload: SyncRequest) -> SyncResponse:
    summary = _sync_service.sync_repositories(payload.repositories)
    return SyncResponse(**summary.to_dict())


@app.get("/repositories", response_model=List[RepositoryOut])
def list_repositories() -> List[RepositoryOut]:
    try:
        rows = _database.list_repositories()
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return [RepositoryOut.from_row(row) for row in rows]


@app.get("/repositories/{repo_id}", response_model=RepositoryOut)
def get_repository(repo_id: int) -> RepositoryOut:
    try:
        row = _database.get_repository(repo_id)
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )
    return RepositoryOut.from_row(row)


@app.get("/sync/status")
def sync_status() -> Dict[str, Any]:
    status_payload = get_last_sync_status()
    if status_payload is None:
        return {
            "message": "No sync has been run in this process yet.",
            "last_sync": None,
        }
    return {"message": "Last sync summary", "last_sync": status_payload}
