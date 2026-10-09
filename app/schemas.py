"""Pydantic models for the optional FastAPI layer."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

REPO_NAME_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


class SyncRequest(BaseModel):
    repositories: List[str] = Field(
        ...,
        min_length=1,
        description="List of repositories in owner/repo format",
    )

    @field_validator("repositories")
    @classmethod
    def validate_repo_names(cls, values: List[str]) -> List[str]:
        cleaned: List[str] = []
        for value in values:
            name = value.strip()
            if not REPO_NAME_PATTERN.match(name):
                raise ValueError(
                    f"Invalid repository name '{value}'. Expected owner/repo"
                )
            cleaned.append(name)
        return cleaned


class SyncItemResult(BaseModel):
    full_name: str
    status: str
    message: str
    repo_id: Optional[int] = None
    action: Optional[str] = None


class SyncResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    unchanged: int
    duration_seconds: float
    results: List[SyncItemResult]


class RepositoryOut(BaseModel):
    repo_id: int
    full_name: str
    name: str
    owner: str
    language: Optional[str] = None
    stars: int
    forks: int
    open_issues: int
    html_url: str
    created_at: str
    updated_at: str
    synced_at: str
    etag: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "RepositoryOut":
        return cls(**row)


class HealthResponse(BaseModel):
    status: str
    database_path: str
    repository_count: int
