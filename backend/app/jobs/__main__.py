"""CLI: python -m app.jobs [--force] [--backup-only] [--retention-only]"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from app.jobs.db_backup import run_full_db_backup
from app.jobs.maintenance import run_daily_maintenance
from app.jobs.project_retention import run_stale_project_retention
from app.jobs.billing_reconcile import run_nightly_billing_reconcile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIStory DB backup / project retention jobs")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if today's maintenance already completed",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="Only run full DB backup (circular overwrite)",
    )
    parser.add_argument(
        "--retention-only",
        action="store_true",
        help="Only run stale project backup+purge (manual/CLI; not scheduled)",
    )
    parser.add_argument(
        "--reconcile-only",
        action="store_true",
        help="Only run nightly billing reconcile (provider actual usage query)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    exclusive = sum(bool(x) for x in (args.backup_only, args.retention_only, args.reconcile_only))
    if exclusive > 1:
        print("Choose at most one of --backup-only / --retention-only / --reconcile-only", file=sys.stderr)
        return 2

    if args.backup_only:
        result = run_full_db_backup()
    elif args.retention_only:
        result = run_stale_project_retention()
    elif args.reconcile_only:
        result = run_nightly_billing_reconcile()
    else:
        result = run_daily_maintenance(force=bool(args.force))

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok", True) and not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
