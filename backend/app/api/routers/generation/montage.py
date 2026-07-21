# -*- coding: utf-8 -*-
"""Generation section routes — symbols pulled from shared module."""
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


class MontageItem(BaseModel):
    url: str
    speed: float = 1.0
    trim_start: float = 0.0
    trim_end: float = 0.0

class MontageRequest(BaseModel):
    items: List[MontageItem]


class MontageDeleteRequest(BaseModel):
    url: str

# --- montage (moved from endpoints) ---
@router.post("/projects/{project_id}/montage")
async def generate_montage(
    project_id: int,
    request: MontageRequest,
    async_mode: bool = Query(False),
    current_user: User = Depends(get_current_user)
):
    try:
        items_payload = [item.dict() for item in request.items]
        if async_mode:
            task_id = _create_task_record(
                user_id=current_user.id,
                kind="montage",
                status="pending",
            )
            _submit_generation_background_task(
                job_id=task_id,
                kind="montage",
                user_id=current_user.id,
                payload={
                    "project_id": int(project_id),
                    "items": items_payload,
                },
            )
            return {"task_id": task_id, "async": True}

        url = create_montage(project_id, items_payload, user_id=current_user.id)
        return {"url": url}
    except Exception as e:
        logger.error(f"Montage failed: {str(e)}")
        detail = str(e)
        lowered = detail.lower()
        if isinstance(e, ValueError):
            raise HTTPException(status_code=400, detail=detail)
        if "busy" in lowered:
            raise HTTPException(status_code=429, detail=detail)
        raise HTTPException(status_code=500, detail=detail)


@router.delete("/projects/{project_id}/montage")
async def delete_montage(
    project_id: int,
    request: MontageDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_project_access(db, int(project_id), current_user)

    raw_url = str(request.url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Montage url is required")

    if "/uploads/" in raw_url:
        relative_path = raw_url.split("/uploads/", 1)[1]
    else:
        relative_path = os.path.basename(raw_url)

    relative_path = str(relative_path or "").replace("\\", "/").lstrip("/")
    filename = os.path.basename(relative_path)
    expected_prefix = f"montage_{int(project_id)}_"
    if not filename or not filename.startswith(expected_prefix) or not filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Invalid montage file")

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    file_path = os.path.abspath(os.path.join(upload_root, relative_path))
    if os.path.commonpath([upload_root, file_path]) != upload_root:
        raise HTTPException(status_code=400, detail="Invalid montage path")

    if not os.path.exists(file_path):
        return {"status": "success", "deleted": False, "message": "Montage file not found"}

    try:
        os.remove(file_path)
    except FileNotFoundError:
        return {"status": "success", "deleted": False, "message": "Montage file not found"}
    except Exception as exc:
        logger.warning("Failed to delete montage file project_id=%s path=%s error=%s", project_id, file_path, exc)
        raise HTTPException(status_code=500, detail="Failed to delete montage file")

    return {"status": "success", "deleted": True, "url": raw_url}


from app.schemas.media_analyze import AnalyzeImageRequest  # noqa: E402,F401



