"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root if present (never commit real secrets).
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN") or None
GITHUB_TIMEOUT: float = float(os.getenv("GITHUB_TIMEOUT", "10"))
GITHUB_MAX_RETRIES: int = int(os.getenv("GITHUB_MAX_RETRIES", "3"))
DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "github_sync.db")))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logging(level: str | None = None) -> None:
    """Configure root logging once for CLI and API entrypoints."""
    log_level = getattr(logging, (level or LOG_LEVEL), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
