"""Record prompt-injection / prompt-leak incidents and notify administrators."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Iterable, List, Optional

from app.core.prompt_injection import PROMPT_INJECTION_DETECTED, PROMPT_LEAK_DETECTED
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.services.script_analysis_ai_diagnosis import OPS_SUPPORT_EMAIL
from app.services.system_log_service import append_ui_system_logs, log_action

logger = logging.getLogger("api_logger")

_KNOWN_CODES = {PROMPT_INJECTION_DETECTED, PROMPT_LEAK_DETECTED}


def _coerce_int(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _user_identity(user: Any) -> tuple[Optional[int], str]:
    if user is None:
        return None, "unknown"
    user_id = _coerce_int(getattr(user, "id", None))
    username = str(
        getattr(user, "username", None)
        or getattr(user, "email", None)
        or (f"user_{user_id}" if user_id else "")
        or "unknown"
    ).strip()
    return user_id, username or "unknown"


def _resolve_scope(
    *,
    episode: Any = None,
    project_id: Any = None,
    episode_id: Any = None,
    scene_id: Any = None,
    db: Any = None,
) -> tuple[Optional[int], Optional[int], Optional[str]]:
    pid = _coerce_int(project_id) or _coerce_int(getattr(episode, "project_id", None))
    eid = _coerce_int(episode_id) or _coerce_int(getattr(episode, "id", None))
    sid = str(scene_id or "").strip() or None
    if pid or not eid:
        return pid, eid, sid

    query_db = db
    owned_session = None
    try:
        if query_db is None:
            owned_session = SessionLocal()
            query_db = owned_session
        from app.models.all_models import Episode

        row = query_db.query(Episode).filter(Episode.id == eid).first()
        pid = _coerce_int(getattr(row, "project_id", None))
    except Exception:
        logger.exception("[prompt_security] failed to resolve project_id from episode_id=%s", eid)
    finally:
        if owned_session is not None:
            try:
                owned_session.close()
            except Exception:
                pass
    return pid, eid, sid


def _match_preview(matches: Optional[Iterable[Dict[str, Any]]]) -> str:
    snippets: List[str] = []
    for item in list(matches or [])[:8]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        snippet = str(item.get("snippet") or "").strip()[:80]
        if not kind and not snippet:
            continue
        snippets.append(f"{kind}:{snippet}" if kind and snippet else (kind or snippet))
    return "；".join(snippets)


def _incident_title(code: str) -> str:
    if code == PROMPT_LEAK_DETECTED:
        return "提示词泄露拦截（水印标签被带出）"
    return "提示词注入拦截"


def collect_admin_notify_emails(db: Any = None) -> List[str]:
    emails: List[str] = []
    seen: set[str] = set()

    def _add(raw: Any) -> None:
        email = str(raw or "").strip()
        if not email or "@" not in email:
            return
        key = email.lower()
        if key in seen:
            return
        seen.add(key)
        emails.append(email)

    _add(OPS_SUPPORT_EMAIL)
    owned_session = None
    query_db = db
    try:
        if query_db is None:
            owned_session = SessionLocal()
            query_db = owned_session
        from app.models.all_models import User

        rows = (
            query_db.query(User)
            .filter(
                (User.is_superuser.is_(True)) | (User.is_system.is_(True)),
                User.is_active == 1,
            )
            .all()
        )
        for row in rows:
            _add(getattr(row, "email", None))
    except Exception:
        logger.exception("[prompt_security] failed to collect admin emails")
    finally:
        if owned_session is not None:
            try:
                owned_session.close()
            except Exception:
                pass
    return emails


def _write_progress_issue(
    *,
    code: str,
    title: str,
    details: str,
    source: str,
    project_id: Optional[int],
    episode_id: Optional[int],
    scene_id: Optional[str],
) -> None:
    if not project_id:
        return
    from app.services.script_analysis_flow import raise_progress_issue

    with SessionLocal() as issue_db:
        raise_progress_issue(
            issue_db,
            project_id=int(project_id),
            issue_code=code,
            title=title,
            severity="BLOCKER",
            owner_domain="security",
            details=details,
            node_ref=source or None,
            episode_id=episode_id,
            scene_id=scene_id,
        )
        issue_db.commit()


def _email_body(
    *,
    code: str,
    title: str,
    message: str,
    source: str,
    preview: str,
    user_id: Optional[int],
    username: str,
    project_id: Optional[int],
    episode_id: Optional[int],
    scene_id: Optional[str],
) -> str:
    return (
        f"{title}\n"
        f"时间：{now_bj_iso()}\n"
        f"代码：{code}\n"
        f"来源：{source or 'unspecified'}\n"
        f"用户：{username} (id={user_id or '-'})\n"
        f"项目：{project_id or '-'}\n"
        f"分集：{episode_id or '-'}\n"
        f"场次：{scene_id or '-'}\n"
        f"说明：{message}\n"
        f"命中：{preview or '-'}\n"
        "内容未落库。请检查该次剧本分析输出与对应技能提示词。\n"
    )


def _notify_admins(
    *,
    code: str,
    title: str,
    message: str,
    source: str,
    preview: str,
    user_id: Optional[int],
    username: str,
    project_id: Optional[int],
    episode_id: Optional[int],
    scene_id: Optional[str],
) -> None:
    recipients = collect_admin_notify_emails()
    if not recipients:
        logger.error("[prompt_security] no admin recipients for %s", code)
        return
    from app.services.auth_email import _send_email_via_runtime_smtp

    subject = f"[AI Story] {title}"
    content = _email_body(
        code=code,
        title=title,
        message=message,
        source=source,
        preview=preview,
        user_id=user_id,
        username=username,
        project_id=project_id,
        episode_id=episode_id,
        scene_id=scene_id,
    )
    for email in recipients:
        try:
            _send_email_via_runtime_smtp(email, subject, content, strict=False)
        except Exception:
            logger.exception("[prompt_security] admin email failed to=%s code=%s", email, code)


def record_prompt_security_incident(
    *,
    code: str,
    message: str,
    source: str = "",
    matches: Optional[List[Dict[str, Any]]] = None,
    db: Any = None,
    episode: Any = None,
    user: Any = None,
    project_id: Any = None,
    episode_id: Any = None,
    scene_id: Any = None,
    notify_admins: bool = True,
) -> None:
    """Best-effort audit + admin notify. Must never raise."""
    try:
        resolved_code = str(code or "").strip() or PROMPT_INJECTION_DETECTED
        if resolved_code not in _KNOWN_CODES:
            resolved_code = PROMPT_INJECTION_DETECTED
        title = _incident_title(resolved_code)
        preview = _match_preview(matches)
        user_id, username = _user_identity(user)
        pid, eid, sid = _resolve_scope(
            episode=episode,
            project_id=project_id,
            episode_id=episode_id,
            scene_id=scene_id,
            db=db,
        )
        details = (
            f"{message}\n"
            f"source={source or 'unspecified'} "
            f"project_id={pid or '-'} episode_id={eid or '-'} scene_id={sid or '-'} "
            f"hits={preview or '-'}"
        )[:4000]

        logger.error(
            "[prompt_security] %s source=%s user=%s project_id=%s episode_id=%s scene_id=%s hits=%s",
            resolved_code,
            source or "unspecified",
            username,
            pid,
            eid,
            sid,
            preview or "-",
        )

        try:
            log_action(
                None,
                user_id or 0,
                username,
                resolved_code,
                details,
            )
        except Exception:
            logger.exception("[prompt_security] system log write failed")
        try:
            append_ui_system_logs(
                [{"type": "error", "message": f"{title}：{message}", "client_time": now_bj_iso()}],
                user_id=user_id,
                user_name=username,
            )
        except Exception:
            logger.exception("[prompt_security] ui system log append failed")

        try:
            _write_progress_issue(
                code=resolved_code,
                title=title,
                details=details,
                source=source or "",
                project_id=pid,
                episode_id=eid,
                scene_id=sid,
            )
        except Exception:
            logger.exception("[prompt_security] progress issue write failed")

        if notify_admins:
            threading.Thread(
                target=_notify_admins,
                kwargs={
                    "code": resolved_code,
                    "title": title,
                    "message": str(message or "").strip(),
                    "source": source or "unspecified",
                    "preview": preview,
                    "user_id": user_id,
                    "username": username,
                    "project_id": pid,
                    "episode_id": eid,
                    "scene_id": sid,
                },
                daemon=True,
                name="prompt-security-notify",
            ).start()
    except Exception:
        logger.exception("[prompt_security] record_prompt_security_incident failed")
