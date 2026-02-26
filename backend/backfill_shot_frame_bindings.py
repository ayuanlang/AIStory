import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

from app.db.session import SessionLocal
from app.models.all_models import Asset, Shot


def _is_blank(value: Optional[str]) -> bool:
    return value is None or str(value).strip() == ""


def _safe_meta(meta: Any) -> Dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            parsed = json.loads(meta)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _norm_frame_type(meta: Dict[str, Any]) -> Optional[str]:
    raw = str(meta.get("frame_type") or meta.get("asset_type") or "").strip().lower()
    if raw in {"start_frame", "start", "first_frame"}:
        return "start"
    if raw in {"end_frame", "end", "last_frame"}:
        return "end"
    return None


def _safe_json_obj(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _pick_shot(
    shot_by_id: Dict[int, Shot],
    shot_by_number_project: Dict[Tuple[Optional[int], str], Shot],
    meta: Dict[str, Any],
) -> Optional[Shot]:
    shot_id_val = meta.get("shot_id")
    if shot_id_val is not None:
        try:
            shot_obj = shot_by_id.get(int(shot_id_val))
            if shot_obj:
                return shot_obj
        except Exception:
            pass

    shot_number = meta.get("shot_number")
    if shot_number is not None:
        project_val = meta.get("project_id")
        project_id = None
        try:
            project_id = int(project_val) if project_val is not None else None
        except Exception:
            project_id = None

        key = (project_id, str(shot_number).strip())
        shot_obj = shot_by_number_project.get(key)
        if shot_obj:
            return shot_obj

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill shot frame bindings from assets metadata."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates to database. Default is dry-run.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing shot.image_url / technical_notes.end_frame_url with newer asset URLs.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        shots: List[Shot] = db.query(Shot).all()
        assets: List[Asset] = db.query(Asset).order_by(Asset.id.asc()).all()

        shot_by_id: Dict[int, Shot] = {s.id: s for s in shots}
        shot_by_number_project: Dict[Tuple[Optional[int], str], Shot] = {}
        for shot in shots:
            if shot.shot_id:
                key = (shot.project_id, str(shot.shot_id).strip())
                if key not in shot_by_number_project:
                    shot_by_number_project[key] = shot

        latest_frame_asset: Dict[Tuple[int, str], str] = {}
        skipped_missing_meta = 0
        skipped_unmatched_shot = 0
        skipped_non_frame_asset = 0

        for asset in assets:
            meta = _safe_meta(asset.meta_info)
            if not meta:
                skipped_missing_meta += 1
                continue

            frame_type = _norm_frame_type(meta)
            if frame_type is None:
                skipped_non_frame_asset += 1
                continue

            shot_obj = _pick_shot(shot_by_id, shot_by_number_project, meta)
            if shot_obj is None:
                skipped_unmatched_shot += 1
                continue

            if not asset.url:
                continue

            latest_frame_asset[(shot_obj.id, frame_type)] = asset.url

        updated_start = 0
        updated_end = 0
        touched_shots = 0

        for shot in shots:
            changed = False

            start_url = latest_frame_asset.get((shot.id, "start"))
            if start_url:
                should_update_start = args.overwrite or _is_blank(shot.image_url)
                if should_update_start and shot.image_url != start_url:
                    shot.image_url = start_url
                    updated_start += 1
                    changed = True

            end_url = latest_frame_asset.get((shot.id, "end"))
            if end_url:
                tech = _safe_json_obj(shot.technical_notes)
                existing_end_url = tech.get("end_frame_url")
                should_update_end = args.overwrite or _is_blank(existing_end_url)
                if should_update_end and existing_end_url != end_url:
                    tech["end_frame_url"] = end_url
                    shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                    updated_end += 1
                    changed = True

            if changed:
                touched_shots += 1

        if args.apply:
            db.commit()

        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[{mode}] shots_total={len(shots)} assets_total={len(assets)}")
        print(
            f"[{mode}] candidate_bindings={len(latest_frame_asset)} "
            f"updated_start={updated_start} updated_end={updated_end} touched_shots={touched_shots}"
        )
        print(
            f"[{mode}] skipped_missing_meta={skipped_missing_meta} "
            f"skipped_non_frame_asset={skipped_non_frame_asset} skipped_unmatched_shot={skipped_unmatched_shot}"
        )

        if not args.apply:
            print("[DRY-RUN] No database changes were committed. Use --apply to persist.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
