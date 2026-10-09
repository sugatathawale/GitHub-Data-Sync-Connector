#!/usr/bin/env python3
"""Command-line entrypoint for the GitHub Data Sync Connector."""

from __future__ import annotations

import argparse
import sys

from app.config import setup_logging
from app.sync_service import SyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize GitHub repository metadata into a local SQLite database."
        )
    )
    parser.add_argument(
        "repositories",
        nargs="+",
        help="One or more repositories in owner/repo format "
        "(example: facebook/react pallets/flask)",
    )
    return parser


def print_summary(summary) -> None:
    print()
    print("=" * 56)
    print("SYNC SUMMARY")
    print("=" * 56)
    for result in summary.results:
        marker = {
            "success": "OK",
            "unchanged": "SKIP",
            "failed": "FAIL",
        }.get(result.status, result.status.upper())
        print(f"[{marker}] {result.full_name}: {result.message}")

    print("-" * 56)
    print(f"Total repositories requested : {summary.total}")
    print(f"Successfully synchronized    : {summary.succeeded}")
    print(f"Unchanged (conditional 304)  : {summary.unchanged}")
    print(f"Failed repositories          : {summary.failed}")
    print(f"Total execution time         : {summary.duration_seconds:.3f}s")
    print("=" * 56)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    service = SyncService()
    summary = service.sync_repositories(args.repositories)
    print_summary(summary)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
