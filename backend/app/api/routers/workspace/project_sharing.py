# -*- coding: utf-8 -*-
"""Project shares + asset-review workspace section routes."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

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

@router.get("/projects/{project_id}/shares", response_model=List[ProjectShareOut])
def list_project_shares(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    rows = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectShare, User)
            .join(User, User.id == ProjectShare.user_id)
            .filter(ProjectShare.project_id == project_id)
            .order_by(ProjectShare.id.desc())
            .all()
        ),
        context="project_share.list",
    )
    return [
        _serialize_project_share(share, user)
        for share, user in rows
    ]


@router.post("/projects/{project_id}/shares", response_model=ProjectShareOut)
def create_project_share(
    project_id: int,
    payload: ProjectShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    target = str(payload.target_user or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target_user is required")

    role = _normalize_project_share_role(payload.role, strict=True)
    permissions = _normalize_project_share_permissions(payload.permissions)

    target_user = db.query(User).filter(or_(User.username == target, User.email == target)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.owner_id == target_user.id:
        raise HTTPException(status_code=400, detail="Project owner already has access")

    existing = _get_project_share_record(db, project_id, target_user.id)
    if existing:
        _apply_project_share_access_fields(existing, role, permissions)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize_project_share(existing, target_user)

    share = _build_project_share(project_id, target_user.id, role, permissions)
    db.add(share)
    db.commit()
    db.refresh(share)
    return _serialize_project_share(share, target_user)


@router.delete("/projects/{project_id}/shares/{shared_user_id}", status_code=204)
def delete_project_share(
    project_id: int,
    shared_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    share = _get_project_share_record(db, project_id, shared_user_id)
    if not share:
        raise HTTPException(status_code=404, detail="Share record not found")
    db.delete(share)
    db.commit()
    return None


@router.get("/projects/{project_id}/review_threads", response_model=List[ProjectAssetReviewThreadOut])
def list_project_review_threads(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    _require_project_access(db, project_id, current_user)
    threads = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectAssetReviewThread)
            .filter(ProjectAssetReviewThread.project_id == project_id)
            .order_by(ProjectAssetReviewThread.latest_activity_at.desc(), ProjectAssetReviewThread.id.desc())
            .all()
        ),
        context="review_thread.list_project",
    )
    user_ids = {thread.requester_user_id for thread in threads} | {thread.reviewer_user_id for thread in threads}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [
        _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)
        for thread in threads
    ]


@router.get("/projects/review_threads/inbox", response_model=List[ProjectAssetReviewThreadOut])
def list_review_inbox_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    threads = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectAssetReviewThread)
            .filter(ProjectAssetReviewThread.reviewer_user_id == current_user.id)
            .order_by(ProjectAssetReviewThread.latest_activity_at.desc(), ProjectAssetReviewThread.id.desc())
            .all()
        ),
        context="review_thread.list_inbox",
    )
    user_ids = {thread.requester_user_id for thread in threads} | {thread.reviewer_user_id for thread in threads}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [
        _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)
        for thread in threads
    ]


@router.get("/projects/review_threads/outbox", response_model=List[ProjectAssetReviewThreadOut])
def list_review_outbox_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    threads = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectAssetReviewThread)
            .filter(ProjectAssetReviewThread.requester_user_id == current_user.id)
            .order_by(ProjectAssetReviewThread.latest_activity_at.desc(), ProjectAssetReviewThread.id.desc())
            .all()
        ),
        context="review_thread.list_outbox",
    )
    user_ids = {thread.requester_user_id for thread in threads} | {thread.reviewer_user_id for thread in threads}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [
        _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)
        for thread in threads
    ]


@router.post("/projects/{project_id}/review_threads", response_model=ProjectAssetReviewThreadOut)
def create_project_review_thread(
    project_id: int,
    payload: ProjectAssetReviewThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    project = _require_project_access(db, project_id, current_user)
    share = _get_project_share_record(db, project_id, current_user.id)
    if share and _normalize_project_share_role(getattr(share, "role", None)) == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot initiate asset reviews")

    reviewer = _resolve_review_reviewer(
        db,
        project,
        current_user,
        payload.reviewer_user_id,
        payload.reviewer_user,
    )
    scope_type = _normalize_asset_review_scope_type(payload.scope_type)
    entity_required = bool(payload.entity_required)
    shot_required = bool(payload.shot_required)
    _ensure_review_scope_has_dimension(entity_required, shot_required)
    entity_ids, shot_ids = _validate_review_target_ids_for_project(
        db,
        project.id,
        payload.entity_ids or [],
        payload.shot_ids or [],
        scope_type=scope_type,
    )
    now_iso = now_bj_iso()
    thread = ProjectAssetReviewThread(
        project_id=project.id,
        requester_user_id=current_user.id,
        reviewer_user_id=reviewer.id,
        title=(str(payload.title or "").strip() or f"{project.title or 'Project'} 资产审核"),
        status="open",
        latest_round_no=1,
        latest_activity_at=now_iso,
        requester_last_read_at=now_iso,
        reviewer_last_read_at=None,
        updated_at=now_iso,
    )
    db.add(thread)
    db.flush()

    round_row = ProjectAssetReviewRound(
        thread_id=thread.id,
        round_no=1,
        initiated_by_user_id=current_user.id,
        request_message=(str(payload.request_message or "").strip() or None),
        scope_type=scope_type,
        entity_required=entity_required,
        shot_required=shot_required,
        entity_decision="pending",
        shot_decision="pending",
        overall_status="pending_reviewer",
        due_at=(str(payload.due_at or "").strip() or None),
        selected_entity_ids=entity_ids,
        selected_shot_ids=shot_ids,
        updated_at=now_iso,
    )
    db.add(round_row)
    db.flush()

    initial_message = ProjectAssetReviewMessage(
        round_id=round_row.id,
        sender_user_id=current_user.id,
        sender_role="requester",
        message_type="request",
        message_text=(str(payload.request_message or "").strip() or None),
        created_at=now_iso,
    )
    db.add(initial_message)
    db.commit()
    db.refresh(thread)
    return _serialize_review_thread(thread, requester=current_user, reviewer=reviewer, current_user=current_user)


@router.get("/review_threads/{thread_id}", response_model=ProjectAssetReviewThreadOut)
def get_review_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, _project = _require_review_thread_access(db, thread_id, current_user)
    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([thread.requester_user_id, thread.reviewer_user_id])).all()
    }
    return _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)


@router.post("/review_threads/{thread_id}/read", response_model=ProjectAssetReviewThreadOut)
def mark_review_thread_read(
    thread_id: int,
    payload: ProjectAssetReviewThreadReadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, _project = _require_review_thread_access(db, thread_id, current_user)
    if payload.read:
        _mark_review_thread_read_for_user(thread, current_user)
        thread.updated_at = now_bj_iso()
        db.add(thread)
        db.commit()
        db.refresh(thread)
    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([thread.requester_user_id, thread.reviewer_user_id])).all()
    }
    return _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)


@router.patch("/review_threads/{thread_id}/status", response_model=ProjectAssetReviewThreadOut)
def update_review_thread_status(
    thread_id: int,
    payload: ProjectAssetReviewThreadStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, project = _require_review_thread_access(db, thread_id, current_user)
    next_status = str(payload.status or "").strip().lower()
    if next_status not in _ASSET_REVIEW_THREAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid review thread status: {next_status}")
    can_archive = int(current_user.id or 0) in {int(thread.requester_user_id or 0), int(project.owner_id or 0)}
    if next_status == "archived" and not can_archive:
        raise HTTPException(status_code=403, detail="Only requester side can archive review threads")

    now_iso = now_bj_iso()
    thread.status = next_status
    thread.updated_at = now_iso
    thread.latest_activity_at = now_iso
    db.add(thread)

    if next_status == "closed":
        db.query(ProjectAssetReviewRound).filter(
            ProjectAssetReviewRound.thread_id == thread.id,
            ProjectAssetReviewRound.closed_at.is_(None),
        ).update(
            {
                ProjectAssetReviewRound.overall_status: "closed",
                ProjectAssetReviewRound.closed_at: now_iso,
                ProjectAssetReviewRound.updated_at: now_iso,
            },
            synchronize_session=False,
        )

    requester = db.query(User).filter(User.id == thread.requester_user_id).first()
    reviewer = db.query(User).filter(User.id == thread.reviewer_user_id).first()
    db.commit()
    db.refresh(thread)
    return _serialize_review_thread(thread, requester=requester, reviewer=reviewer)


@router.get("/review_threads/{thread_id}/rounds", response_model=List[ProjectAssetReviewRoundOut])
def list_review_thread_rounds(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, _project = _require_review_thread_access(db, thread_id, current_user)
    rounds = (
        db.query(ProjectAssetReviewRound)
        .filter(ProjectAssetReviewRound.thread_id == thread.id)
        .order_by(ProjectAssetReviewRound.round_no.asc(), ProjectAssetReviewRound.id.asc())
        .all()
    )
    user_ids = {row.initiated_by_user_id for row in rounds}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [_serialize_review_round(row, initiator=users.get(row.initiated_by_user_id)) for row in rounds]


@router.post("/review_threads/{thread_id}/rounds", response_model=ProjectAssetReviewRoundOut)
def create_review_thread_round(
    thread_id: int,
    payload: ProjectAssetReviewRoundCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, project = _require_review_thread_access(db, thread_id, current_user)
    sender_role = _resolve_thread_sender_role(db, thread, current_user, project)
    if sender_role != "requester":
        raise HTTPException(status_code=403, detail="Only requester side can initiate a new review round")

    scope_type = _normalize_asset_review_scope_type(payload.scope_type)
    entity_required = bool(payload.entity_required)
    shot_required = bool(payload.shot_required)
    _ensure_review_scope_has_dimension(entity_required, shot_required)
    entity_ids, shot_ids = _validate_review_target_ids_for_project(
        db,
        project.id,
        payload.entity_ids or [],
        payload.shot_ids or [],
        scope_type=scope_type,
    )
    next_round_no = int(thread.latest_round_no or 0) + 1
    now_iso = now_bj_iso()
    round_row = ProjectAssetReviewRound(
        thread_id=thread.id,
        round_no=next_round_no,
        initiated_by_user_id=current_user.id,
        request_message=(str(payload.request_message or "").strip() or None),
        scope_type=scope_type,
        entity_required=entity_required,
        shot_required=shot_required,
        entity_decision="pending",
        shot_decision="pending",
        overall_status="pending_reviewer",
        due_at=(str(payload.due_at or "").strip() or None),
        selected_entity_ids=entity_ids,
        selected_shot_ids=shot_ids,
        updated_at=now_iso,
    )
    db.add(round_row)
    db.flush()
    db.add(ProjectAssetReviewMessage(
        round_id=round_row.id,
        sender_user_id=current_user.id,
        sender_role="requester",
        message_type="request",
        message_text=(str(payload.request_message or "").strip() or None),
        created_at=now_iso,
    ))
    thread.latest_round_no = next_round_no
    thread.latest_activity_at = now_iso
    _mark_review_thread_read_for_user(thread, current_user, read_at=now_iso)
    thread.updated_at = now_iso
    thread.status = "open"
    db.add(thread)
    db.commit()
    db.refresh(round_row)
    return _serialize_review_round(round_row, initiator=current_user)


@router.get("/review_rounds/{round_id}/messages", response_model=List[ProjectAssetReviewMessageOut])
def list_review_round_messages(
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    round_row, _thread, _project = _require_review_round_access(db, round_id, current_user)
    messages = (
        db.query(ProjectAssetReviewMessage)
        .filter(ProjectAssetReviewMessage.round_id == round_row.id)
        .order_by(ProjectAssetReviewMessage.id.asc())
        .all()
    )
    user_ids = {message.sender_user_id for message in messages}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [_serialize_review_message(message, sender=users.get(message.sender_user_id)) for message in messages]


@router.post("/review_rounds/{round_id}/messages", response_model=ProjectAssetReviewMessageOut)
def create_review_round_message(
    round_id: int,
    payload: ProjectAssetReviewMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    round_row, thread, project = _require_review_round_access(db, round_id, current_user)
    sender_role = _resolve_thread_sender_role(db, thread, current_user, project)
    message_type = _normalize_asset_review_message_type(payload.message_type)
    message_text = (str(payload.message_text or "").strip() or None)
    entity_feedback = (str(payload.entity_feedback or "").strip() or None)
    shot_feedback = (str(payload.shot_feedback or "").strip() or None)
    entity_decision = _normalize_asset_review_decision(payload.entity_decision)
    shot_decision = _normalize_asset_review_decision(payload.shot_decision)

    if sender_role != "reviewer" and (entity_decision or shot_decision):
        raise HTTPException(status_code=403, detail="Only reviewer can submit review decisions")
    if sender_role == "reviewer" and message_type == "message" and (entity_decision or shot_decision):
        message_type = "reply"
    if sender_role == "requester" and message_type == "message":
        message_type = "followup"
    if not any([message_text, entity_feedback, shot_feedback, entity_decision, shot_decision]):
        raise HTTPException(status_code=400, detail="Message body or review feedback is required")

    now_iso = now_bj_iso()
    if sender_role == "reviewer":
        if round_row.entity_required and entity_decision:
            round_row.entity_decision = entity_decision
        if round_row.shot_required and shot_decision:
            round_row.shot_decision = shot_decision
        if entity_feedback is not None:
            round_row.entity_feedback = entity_feedback
        if shot_feedback is not None:
            round_row.shot_feedback = shot_feedback
        round_row.overall_status = "replied"
        round_row.closed_at = now_iso if (
            (not round_row.entity_required or round_row.entity_decision != "pending")
            and (not round_row.shot_required or round_row.shot_decision != "pending")
        ) else None
        _mark_review_thread_read_for_user(thread, current_user, read_at=now_iso)
    else:
        round_row.overall_status = "in_discussion" if round_row.overall_status != "pending_reviewer" else round_row.overall_status
        _mark_review_thread_read_for_user(thread, current_user, read_at=now_iso)

    round_row.updated_at = now_iso
    thread.latest_activity_at = now_iso
    thread.updated_at = now_iso
    thread.status = "open"

    message = ProjectAssetReviewMessage(
        round_id=round_row.id,
        sender_user_id=current_user.id,
        sender_role=sender_role,
        message_type=message_type,
        message_text=message_text,
        entity_decision=entity_decision,
        shot_decision=shot_decision,
        entity_feedback=entity_feedback,
        shot_feedback=shot_feedback,
        created_at=now_iso,
    )
    db.add(round_row)
    db.add(thread)
    db.add(message)
    db.commit()
    db.refresh(message)
    return _serialize_review_message(message, sender=current_user)


