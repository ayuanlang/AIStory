"""Admin APIs for manual stale-project backup and hard purge."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.jobs.project_retention import list_stale_project_candidates, purge_projects_by_ids
from app.models.all_models import User

router = APIRouter(tags=["admin-project-retention"])


class ProjectRetentionCandidateOut(BaseModel):
    project_id: int
    title: str
    owner_id: Optional[int] = None
    owner_username: Optional[str] = None
    owner_email: Optional[str] = None
    is_deleted: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    idle_days: Optional[int] = None
    episode_count: int = 0
    scene_count: int = 0
    shot_count: int = 0
    entity_count: int = 0
    asset_count: int = 0


class ProjectRetentionCandidatesOut(BaseModel):
    ok: bool = True
    retention_days: int
    require_soft_deleted: bool
    cutoff_at: str
    total_count: int
    projects: List[ProjectRetentionCandidateOut]
    project_backup_dir: str


class ProjectRetentionPurgeRequest(BaseModel):
    project_ids: List[int] = Field(default_factory=list)
    retention_days: Optional[int] = None
    require_soft_deleted: Optional[bool] = None


class ProjectRetentionPurgeOut(BaseModel):
    ok: bool
    retention_days: int
    require_soft_deleted: bool
    requested_count: int
    purged_count: int
    skipped_count: int
    purged: list
    skipped: list
    errors: list
    created_at: str


def _require_superuser(user: User) -> None:
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Only superuser can manage project retention")


@router.get("/admin/project-retention/candidates", response_model=ProjectRetentionCandidatesOut)
def get_project_retention_candidates(
    retention_days: Optional[int] = Query(None, ge=1, le=3650),
    require_soft_deleted: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superuser(current_user)
    _ = db  # auth/session warm; listing opens its own sessions
    days = int(retention_days if retention_days is not None else settings.PROJECT_RETENTION_DAYS)
    payload = list_stale_project_candidates(
        retention_days=days,
        require_soft_deleted=require_soft_deleted,
    )
    return ProjectRetentionCandidatesOut(**payload)


@router.post("/admin/project-retention/purge", response_model=ProjectRetentionPurgeOut)
def post_project_retention_purge(
    req: ProjectRetentionPurgeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superuser(current_user)
    _ = db
    project_ids = [int(x) for x in (req.project_ids or []) if str(x).strip()]
    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids is required")
    if len(project_ids) > 500:
        raise HTTPException(status_code=400, detail="Too many project_ids (max 500 per request)")

    result = purge_projects_by_ids(
        project_ids,
        retention_days=req.retention_days,
        require_soft_deleted=req.require_soft_deleted,
        allow_non_stale=False,
    )
    return ProjectRetentionPurgeOut(**result)
