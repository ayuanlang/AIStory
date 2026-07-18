"""Daily full-database backup with circular overwrite."""

from __future__ import annotations

import gzip
import json
import logging
import os
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, unquote

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.time_utils import now_bj
from app.db.session import SessionLocal, engine, is_sqlite

logger = logging.getLogger(__name__)

_BACKUP_NAME_RE = re.compile(r"^aistory_(\d{8})(?:_\d{6})?\.(?:dump|sql\.gz|db|jsonl\.gz)$")


def _ensure_backup_dir() -> Path:
    path = Path(settings.DB_BACKUP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stamp() -> str:
    return now_bj().strftime("%Y%m%d")


def _stamp_with_time() -> str:
    return now_bj().strftime("%Y%m%d_%H%M%S")


def _postgres_dsn() -> str:
    dsn = str(settings.DATABASE_URL or "").strip()
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
    return dsn


def _sqlite_db_path() -> Optional[Path]:
    url = str(settings.DATABASE_URL or "")
    if not url.startswith("sqlite"):
        return None
    # sqlite:////abs/path or sqlite:///relative
    raw = url.split("sqlite:///", 1)[-1]
    if raw.startswith("/") and os.name == "nt" and len(raw) > 2 and raw[2] == ":":
        # sqlite:////C:/... becomes /C:/...
        raw = raw.lstrip("/")
    path = Path(unquote(raw))
    if not path.is_absolute():
        path = (settings.BASE_DIR / path).resolve()
    return path


def _apply_circular_overwrite(backup_dir: Path, keep_count: int) -> List[str]:
    candidates: List[Path] = []
    for item in backup_dir.iterdir():
        if not item.is_file():
            continue
        if _BACKUP_NAME_RE.match(item.name):
            candidates.append(item)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed: List[str] = []
    for stale in candidates[keep_count:]:
        try:
            stale.unlink(missing_ok=True)
            removed.append(stale.name)
        except Exception as exc:
            logger.warning("DB backup circular overwrite failed for %s: %s", stale, exc)
    return removed


def _backup_sqlite(dest: Path) -> Path:
    src = _sqlite_db_path()
    if src is None or not src.exists():
        raise FileNotFoundError(f"SQLite database not found: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Prefer online backup API so WAL contents are included safely.
    with sqlite3.connect(str(src)) as source_conn:
        with sqlite3.connect(str(dest)) as dest_conn:
            source_conn.backup(dest_conn)
    return dest


def _try_pg_dump(dest: Path) -> Optional[Path]:
    dsn = _postgres_dsn()
    parsed = urlparse(dsn)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        f"--dbname={dsn}",
        f"--file={dest}",
    ]
    try:
        completed = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60 * 30,
            check=False,
        )
    except FileNotFoundError:
        logger.info("pg_dump not available; falling back to SQLAlchemy dump")
        return None
    except Exception as exc:
        logger.warning("pg_dump invocation failed: %s", exc)
        return None
    if completed.returncode != 0:
        logger.warning(
            "pg_dump failed (code=%s): %s",
            completed.returncode,
            (completed.stderr or completed.stdout or "")[:800],
        )
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    return dest


def _row_to_jsonable(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, (str, int, float, bool)):
        return row
    if isinstance(row, (bytes, bytearray, memoryview)):
        return bytes(row).hex()
    if isinstance(row, datetime):
        return row.isoformat()
    try:
        json.dumps(row)
        return row
    except Exception:
        return str(row)


def _backup_via_sqlalchemy(dest_jsonl_gz: Path) -> Path:
    """Portable full-table dump used when pg_dump is unavailable."""
    insp = inspect(engine)
    table_names = sorted(insp.get_table_names())
    dest_jsonl_gz.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest_jsonl_gz, "wt", encoding="utf-8") as fh, SessionLocal() as db:
        meta = {
            "type": "aistory_full_db_backup",
            "created_at": now_bj().isoformat(timespec="seconds"),
            "timezone": "Asia/Shanghai",
            "dialect": str(engine.url.get_backend_name() or ""),
            "tables": table_names,
        }
        fh.write(json.dumps({"__meta__": meta}, ensure_ascii=False) + "\n")
        for table in table_names:
            try:
                result = db.execute(text(f'SELECT * FROM "{table}"'))
                columns = list(result.keys())
                count = 0
                for row in result:
                    mapping = {col: _row_to_jsonable(val) for col, val in zip(columns, row)}
                    fh.write(
                        json.dumps(
                            {"table": table, "row": mapping},
                            ensure_ascii=False,
                            default=str,
                        )
                        + "\n"
                    )
                    count += 1
                fh.write(
                    json.dumps({"table": table, "__count__": count}, ensure_ascii=False) + "\n"
                )
            except Exception as exc:
                logger.warning("SQLAlchemy backup skipped table %s: %s", table, exc)
                fh.write(
                    json.dumps(
                        {"table": table, "__error__": str(exc)},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    return dest_jsonl_gz


def run_full_db_backup(*, keep_count: Optional[int] = None) -> Dict[str, Any]:
    """Create today's full DB backup and prune older backups (circular overwrite)."""
    backup_dir = _ensure_backup_dir()
    keep = int(keep_count if keep_count is not None else settings.DB_BACKUP_KEEP_COUNT)
    stamp = _stamp()
    created: Optional[str] = None
    method = "unknown"

    if is_sqlite:
        dest = backup_dir / f"aistory_{stamp}.db"
        if dest.exists():
            dest = backup_dir / f"aistory_{_stamp_with_time()}.db"
        _backup_sqlite(dest)
        created = dest.name
        method = "sqlite_backup"
    else:
        dump_dest = backup_dir / f"aistory_{stamp}.dump"
        if dump_dest.exists():
            dump_dest = backup_dir / f"aistory_{_stamp_with_time()}.dump"
        dumped = _try_pg_dump(dump_dest)
        if dumped is not None:
            created = dumped.name
            method = "pg_dump"
        else:
            jsonl_dest = backup_dir / f"aistory_{stamp}.jsonl.gz"
            if jsonl_dest.exists():
                jsonl_dest = backup_dir / f"aistory_{_stamp_with_time()}.jsonl.gz"
            _backup_via_sqlalchemy(jsonl_dest)
            created = jsonl_dest.name
            method = "sqlalchemy_jsonl"

    removed = _apply_circular_overwrite(backup_dir, keep)
    result = {
        "ok": True,
        "method": method,
        "backup_dir": str(backup_dir),
        "created": created,
        "removed": removed,
        "keep_count": keep,
        "created_at": now_bj().isoformat(timespec="seconds"),
    }
    logger.info(
        "DB backup complete | method=%s created=%s removed=%s keep=%s",
        method,
        created,
        len(removed),
        keep,
    )
    return result
