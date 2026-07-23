# -*- coding: utf-8 -*-
"""Generation job-pool / stop / repair / delete section routes."""
from __future__ import annotations

from app.api.routers.generation import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)

from app.services.generation_job_pool import (  # noqa: E402,F401
    _parse_iso_datetime,
    _normalize_batch_job_status,
    _extract_target_id_from_job_id,
    _build_batch_job_item,
    collect_generation_job_pool,
    repair_generation_job_history as _repair_generation_job_history_impl,
    stop_generation_job as _stop_generation_job_impl,
    delete_generation_job as _delete_generation_job_impl,
    stop_all_generation_jobs as _stop_all_generation_jobs_impl,
)
@router.get("/generate/jobs/pool")
def get_generation_job_pool(
    kind: str = "all",
    running_only: bool = False,
    limit: int = 200,
    shot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return collect_generation_job_pool(
        db=db,
        current_user=current_user,
        kind=kind,
        running_only=running_only,
        limit=limit,
        shot_id=shot_id,
    )


@router.post("/generate/jobs/repair-history")
def repair_generation_job_history(
    kind: str = "all",
    older_than_minutes: int = 120,
    dry_run: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _repair_generation_job_history_impl(
        db=db,
        current_user=current_user,
        kind=kind,
        older_than_minutes=older_than_minutes,
        dry_run=dry_run,
    )


@router.post("/generate/jobs/{kind}/{job_id}/stop")
def stop_generation_job(
    kind: str,
    job_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _stop_generation_job_impl(
        db=db,
        current_user=current_user,
        kind=kind,
        job_id=job_id,
        force=force,
    )


@router.delete("/generate/jobs/{kind}/{job_id}")
def delete_generation_job(
    kind: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _delete_generation_job_impl(
        db=db,
        current_user=current_user,
        kind=kind,
        job_id=job_id,
    )


@router.post("/generate/jobs/stop-all")
def stop_all_generation_jobs(
    kind: str = "all",
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _stop_all_generation_jobs_impl(
        db=db,
        current_user=current_user,
        kind=kind,
        force=force,
    )
