# -*- coding: utf-8 -*-
"""Episode edit-bay routes."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.api.routers.workspace import shared as _shared

router = _shared.router
globals().update({k: v for k, v in vars(_shared).items() if k not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}})


class EditShotRequest(BaseModel):
    shot_ids: List[int]
    system_api_id: Optional[int] = None
    with_score: bool = False


def _episode_for_edit(episode_id: int, db: Session, current_user: User) -> Episode:
    from sqlalchemy.orm import load_only

    episode = (
        db.query(Episode)
        .options(load_only(Episode.id, Episode.project_id, Episode.episode_info))
        .filter(Episode.id == int(episode_id), _active_episode_clause())
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return episode


@router.post("/episodes/{episode_id}/edit/subtitles")
async def recognize_episode_subtitles(
    episode_id: int,
    body: EditShotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.edit_bay import recognize_shot_subtitles

    episode = _episode_for_edit(episode_id, db, current_user)
    return await recognize_shot_subtitles(
        db,
        episode=episode,
        shot_ids=body.shot_ids,
        user=current_user,
        system_api_id=body.system_api_id,
    )


@router.post("/episodes/{episode_id}/edit/merge")
async def merge_episode_edit(
    episode_id: int,
    body: EditShotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.edit_bay import merge_episode_cut

    episode = _episode_for_edit(episode_id, db, current_user)
    return merge_episode_cut(
        db,
        episode=episode,
        project_id=int(episode.project_id),
        shot_ids=body.shot_ids,
        user=current_user,
        with_score=bool(body.with_score),
    )
