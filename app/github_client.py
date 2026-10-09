"""GitHub REST API client with retries, rate-limit handling, and ETag support."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from app.config import (
    GITHUB_API_BASE,
    GITHUB_MAX_RETRIES,
    GITHUB_TIMEOUT,
    GITHUB_TOKEN,
)

logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Base error for GitHub client failures."""


class NotFoundError(GitHubClientError):
    """Repository was not found (HTTP 404)."""


class AuthError(GitHubClientError):
    """Authentication or permission failure (HTTP 401/403)."""


class RateLimitError(GitHubClientError):
    """GitHub rate limit exceeded (HTTP 429) after retries."""


class ServerError(GitHubClientError):
    """GitHub server error (HTTP 5xx) after retries."""


class NetworkError(GitHubClientError):
    """Network timeout or connection failure after retries."""


class InvalidResponseError(GitHubClientError):
    """Response body is not valid JSON or is missing expected shape."""


class InvalidRepoNameError(GitHubClientError):
    """Repository name is not in owner/repo format."""


@dataclass
class FetchResult:
    """Outcome of a repository fetch request."""

    status: str  # "ok" | "not_modified"
    data: dict[str, Any] | None = None
    etag: str | None = None


def _parse_repo_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise InvalidRepoNameError(
            f"Invalid repository name '{full_name}'. Expected format: owner/repo"
        )
    return parts[0], parts[1]


def _build_headers(etag: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-data-sync-connector",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if etag:
        headers["If-None-Match"] = etag
    return headers


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    """Prefer Retry-After header; otherwise use exponential backoff."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return min(2**attempt, 30)


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


class GitHubClient:
    """Thin wrapper around the GitHub Repositories API."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: float = GITHUB_TIMEOUT,
        max_retries: int = GITHUB_MAX_RETRIES,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries

    def fetch_repository(
        self, full_name: str, etag: str | None = None
    ) -> FetchResult:
        """
        Fetch repository metadata from GitHub.

        If etag is provided and the resource is unchanged, returns status
        'not_modified' without a JSON body (HTTP 304).
        """
        owner, repo = _parse_repo_name(full_name)
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        headers = _build_headers(etag)

        last_error: Exception | None = None
        attempts = self.max_retries + 1

        for attempt in range(attempts):
            try:
                logger.info(
                    "Fetching repository %s (attempt %s/%s)",
                    full_name,
                    attempt + 1,
                    attempts,
                )
                response = self.session.get(
                    url, headers=headers, timeout=self.timeout
                )
            except requests.Timeout as exc:
                last_error = NetworkError(f"Request timed out for {full_name}")
                logger.warning("Timeout fetching %s: %s", full_name, exc)
                if attempt < self.max_retries:
                    sleep_for = min(2**attempt, 30)
                    logger.info("Retrying after %.1fs", sleep_for)
                    time.sleep(sleep_for)
                    continue
                raise last_error from exc
            except requests.ConnectionError as exc:
                last_error = NetworkError(f"Connection failed for {full_name}")
                logger.warning("Connection error fetching %s: %s", full_name, exc)
                if attempt < self.max_retries:
                    sleep_for = min(2**attempt, 30)
                    logger.info("Retrying after %.1fs", sleep_for)
                    time.sleep(sleep_for)
                    continue
                raise last_error from exc
            except requests.RequestException as exc:
                raise NetworkError(f"Request failed for {full_name}: {exc}") from exc

            if response.status_code == 304:
                logger.info("Repository %s not modified (304)", full_name)
                return FetchResult(status="not_modified", etag=etag)

            if response.status_code == 404:
                raise NotFoundError(f"Repository not found: {full_name}")

            if response.status_code in (401, 403):
                # Do not log Authorization headers or token values.
                raise AuthError(
                    f"Authentication/authorization failed for {full_name} "
                    f"(HTTP {response.status_code}). Check GITHUB_TOKEN if set."
                )

            if _is_retryable_status(response.status_code):
                wait = _retry_after_seconds(response, attempt)
                message = (
                    f"Transient HTTP {response.status_code} for {full_name}"
                )
                logger.warning("%s; waiting %.1fs before retry", message, wait)
                last_error = (
                    RateLimitError(message)
                    if response.status_code == 429
                    else ServerError(message)
                )
                if attempt < self.max_retries:
                    time.sleep(wait)
                    continue
                raise last_error

            if response.status_code >= 400:
                raise GitHubClientError(
                    f"Unexpected HTTP {response.status_code} for {full_name}"
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise InvalidResponseError(
                    f"Invalid JSON response for {full_name}"
                ) from exc

            if not isinstance(data, dict):
                raise InvalidResponseError(
                    f"Expected a JSON object for {full_name}"
                )

            response_etag = response.headers.get("ETag")
            logger.info("Fetched repository %s successfully", full_name)
            return FetchResult(status="ok", data=data, etag=response_etag)

        # Defensive fallback; loop should always return or raise.
        raise last_error or NetworkError(f"Failed to fetch {full_name}")
