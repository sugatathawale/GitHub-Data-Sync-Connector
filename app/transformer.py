"""Transform raw GitHub API payloads into clean repository records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class TransformError(Exception):
    """Raised when a GitHub payload cannot be transformed safely."""


REQUIRED_FIELDS = ("id", "name", "full_name", "html_url", "created_at", "updated_at")


def _as_int(value: Any, field_name: str, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TransformError(f"Field '{field_name}' must be an integer") from exc


def _as_str(value: Any, field_name: str) -> str:
    if value is None or value == "":
        raise TransformError(f"Field '{field_name}' is required")
    return str(value)


def transform_repository(
    raw: dict[str, Any], etag: str | None = None
) -> dict[str, Any]:
    """
    Convert a GitHub repository JSON object into a clean dictionary.

    Only selected fields are kept. Missing optional values are handled safely.
    """
    if not isinstance(raw, dict):
        raise TransformError("API response must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise TransformError(f"Missing required fields: {', '.join(missing)}")

    owner_data = raw.get("owner")
    if isinstance(owner_data, dict):
        owner = owner_data.get("login")
    else:
        owner = None

    if not owner:
        # Fallback: derive owner from full_name when owner object is incomplete.
        full_name = str(raw.get("full_name", ""))
        owner = full_name.split("/")[0] if "/" in full_name else None

    if not owner:
        raise TransformError("Could not determine repository owner")

    language = raw.get("language")
    if language is not None:
        language = str(language)

    synced_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    return {
        "repo_id": _as_int(raw["id"], "id"),
        "full_name": _as_str(raw["full_name"], "full_name"),
        "name": _as_str(raw["name"], "name"),
        "owner": str(owner),
        "language": language,
        "stars": _as_int(raw.get("stargazers_count"), "stargazers_count"),
        "forks": _as_int(raw.get("forks_count"), "forks_count"),
        "open_issues": _as_int(raw.get("open_issues_count"), "open_issues_count"),
        "html_url": _as_str(raw["html_url"], "html_url"),
        "created_at": _as_str(raw["created_at"], "created_at"),
        "updated_at": _as_str(raw["updated_at"], "updated_at"),
        "synced_at": synced_at,
        "etag": etag,
    }
