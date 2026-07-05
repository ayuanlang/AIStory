"""Batch backfill width/height/resolution metadata for assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from app.db.session import SessionLocal
from app.models.all_models import Asset
from app.services.asset_meta_probe import asset_meta_needs_probe, enrich_asset_meta_info


def _asset_meta_dict(raw_meta: Any) -> Dict[str, Any]:
    if isinstance(raw_meta, dict):
        return dict(raw_meta)
    if isinstance(raw_meta, str):
        try:
            parsed = json.loads(raw_meta)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def backfill(*, limit: int, overwrite: bool, dry_run: bool) -> dict:
    safe_limit = max(1, min(int(limit), 5000))
    db = SessionLocal()
    updated_ids: list[int] = []
    skipped = 0
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.is_deleted.is_(False))
            .order_by(Asset.id.desc())
            .limit(safe_limit)
            .all()
        )
        for asset in assets:
            current_meta = _asset_meta_dict(getattr(asset, "meta_info", None))
            media_kind = str(getattr(asset, "type", "") or "")
            needs_probe = asset_meta_needs_probe(current_meta, media_kind or "image")
            if not needs_probe and not overwrite:
                skipped += 1
                continue
            if dry_run:
                updated_ids.append(int(asset.id))
                continue

            enriched_meta = enrich_asset_meta_info(
                current_meta,
                url=str(getattr(asset, "url", "") or ""),
                media_kind=media_kind,
                overwrite=overwrite,
            )
            if enriched_meta != current_meta:
                asset.meta_info = enriched_meta
                updated_ids.append(int(asset.id))
            else:
                skipped += 1

        if not dry_run and updated_ids:
            db.commit()
        return {
            "ok": True,
            "dry_run": dry_run,
            "scanned": len(assets),
            "updated": len(updated_ids),
            "skipped": skipped,
            "asset_ids": updated_ids[:50],
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill asset metadata")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = backfill(limit=args.limit, overwrite=args.overwrite, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
