# -*- coding: utf-8 -*-
"""SMTP / auth email helpers (shared by auth router and admin ops)."""
from __future__ import annotations

import html
import logging
import os
import re
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any, Dict, Optional

from sqlalchemy import inspect

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import all_models as models
from app.schemas.user_auth import EMAIL_VERIFICATION_TRIAL_CREDITS

logger = logging.getLogger("api_logger")
SMTPSystemConfig = models.SMTPSystemConfig

def _is_valid_email_format(email: str) -> bool:
    raw = (email or "").strip()
    if not raw:
        return False
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", raw))


def _generate_email_verification_code() -> str:
    return f"{uuid.uuid4().int % 1000000:06d}"


def _resolve_runtime_smtp_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "host": str(settings.SMTP_HOST or "").strip(),
        "port": int(settings.SMTP_PORT or 587),
        "username": str(settings.SMTP_USERNAME or "").strip(),
        "password": str(settings.SMTP_PASSWORD or "").strip(),
        "use_ssl": os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
        "use_tls": bool(settings.SMTP_USE_TLS),
        "from_email": str(settings.SMTP_FROM_EMAIL or "").strip(),
        "frontend_base_url": str(settings.FRONTEND_BASE_URL or "").strip(),
    }

    db = SessionLocal()
    try:
        if not inspect(db.connection()).has_table("smtp_system_configs"):
            return config
        setting = db.query(SMTPSystemConfig).filter(
            SMTPSystemConfig.is_active == True,
        ).order_by(SMTPSystemConfig.id.desc()).first()
        if setting:
            config["host"] = str(setting.host or config["host"] or "").strip()
            try:
                config["port"] = int(setting.port or config["port"])
            except Exception:
                pass
            config["username"] = str(setting.username or config["username"] or "").strip()
            config["password"] = str(setting.password or config["password"] or "").strip()
            config["use_ssl"] = bool(setting.use_ssl)
            config["use_tls"] = bool(setting.use_tls)
            config["from_email"] = str(setting.from_email or config["from_email"] or "").strip()
            config["frontend_base_url"] = str(setting.frontend_base_url or config["frontend_base_url"] or "").strip()
    except Exception as e:
        logger.warning("Failed to load runtime SMTP config from DB, fallback to env: %s", e)
    finally:
        db.close()

    if not config["from_email"]:
        config["from_email"] = config["username"]

    return config


def _send_email_via_runtime_smtp(
    to_email: str,
    subject: str,
    content: str,
    *,
    html_content: Optional[str] = None,
    strict: bool = False,
) -> None:
    smtp_cfg = _resolve_runtime_smtp_config()
    smtp_host = str(smtp_cfg.get("host") or "").strip()
    smtp_user = str(smtp_cfg.get("username") or "").strip()
    smtp_pass = str(smtp_cfg.get("password") or "").strip()
    from_email = str(smtp_cfg.get("from_email") or smtp_user or "").strip()
    smtp_port = int(smtp_cfg.get("port") or 587)
    smtp_use_ssl = bool(smtp_cfg.get("use_ssl", False))
    smtp_use_tls = bool(smtp_cfg.get("use_tls", True))
    frontend_base_url = str(smtp_cfg.get("frontend_base_url") or "").strip()

    missing_fields = []
    if not smtp_host:
        missing_fields.append("host")
    if not from_email:
        missing_fields.append("from_email/username")

    if missing_fields:
        message = f"SMTP not configured, missing: {', '.join(missing_fields)}"
        logger.warning("%s. Skip sending email to %s", message, to_email)
        if strict:
            raise RuntimeError(message)
        return

    frontend_base_url_display = frontend_base_url or "(not configured)"
    final_text_content = (
        f"Frontend Base URL: {frontend_base_url_display}\n\n"
        f"{str(content or '')}\n\n"
        f"Frontend Base URL:\n{frontend_base_url_display}\n"
    )

    raw_html_content = str(html_content or "").strip()
    safe_url = html.escape(frontend_base_url_display, quote=True)
    if frontend_base_url:
        footer_line = (
            f"<a href=\"{safe_url}\" target=\"_blank\" rel=\"noopener noreferrer\">{safe_url}</a>"
        )
    else:
        footer_line = safe_url
    footer_html = (
        "<hr style=\"border:none;border-top:1px solid #e5e7eb;margin:16px 0;\">"
        f"<p style=\"color:#6b7280;font-size:12px;\">Frontend Base URL: {footer_line}</p>"
    )
    header_html = (
        "<div style=\"margin:0 0 12px 0;padding:10px 12px;border:1px solid #e5e7eb;"
        "background:#f9fafb;border-radius:6px;color:#111827;font-size:13px;\">"
        f"Frontend Base URL: {footer_line}"
        "</div>"
    )
    if raw_html_content:
        body_close_idx = raw_html_content.lower().rfind("</body>")
        html_close_idx = raw_html_content.lower().rfind("</html>")
        if body_close_idx != -1:
            html_body = (
                f"{raw_html_content[:body_close_idx]}"
                f"{header_html}{footer_html}"
                f"{raw_html_content[body_close_idx:]}"
            )
        elif html_close_idx != -1:
            html_body = (
                f"{raw_html_content[:html_close_idx]}"
                f"{header_html}{footer_html}"
                f"{raw_html_content[html_close_idx:]}"
            )
        else:
            html_body = f"{header_html}{raw_html_content}{footer_html}"
    else:
        html_text = html.escape(str(content or ""))
        html_body = (
            f"{header_html}"
            f"<div style=\"white-space:pre-wrap;font-size:14px;line-height:1.6;color:#111827;\">{html_text}</div>"
            f"{footer_html}"
        )

    text_preview = final_text_content[:300].replace("\n", "\\n")
    html_preview = html_body[:300].replace("\n", " ") if html_body else ""
    logger.warning("SMTP email footer injected | to=%s frontend_base_url=%s", to_email, frontend_base_url_display)
    logger.warning(
        "SMTP payload preview | to=%s text_len=%s html_len=%s text_preview=%s html_preview=%s",
        to_email,
        len(final_text_content or ""),
        len(html_body or ""),
        text_preview,
        html_preview,
    )
    print(
        "[SMTP_DEBUG] "
        f"to={to_email} frontend_base_url={frontend_base_url_display} "
        f"text_len={len(final_text_content or '')} html_len={len(html_body or '')} "
        f"text_preview={text_preview} html_preview={html_preview}"
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(final_text_content)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    if smtp_use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(message)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if smtp_use_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(message)


def send_email_verification_code(to_email: str, code: str) -> None:
    content = (
        "Your AI Story verification code is:\n\n"
        f"{code}\n\n"
        "This code expires in 10 minutes."
    )
    _send_email_via_runtime_smtp(to_email, "AI Story Email Verification Code", content)


def send_welcome_trial_credits_email(to_email: str) -> None:
    content = (
        "Welcome to AI Story!\n\n"
        f"Your email has been verified successfully. We have gifted {EMAIL_VERIFICATION_TRIAL_CREDITS} trial credits to your account.\n\n"
        "You are welcome to start exploring now.\n"
        "If you submit valid issues and suggestions, we may grant additional credits as rewards.\n\n"
        "Thank you for trying AI Story."
    )
    _send_email_via_runtime_smtp(to_email, "Welcome to AI Story - Trial Credits Granted", content)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    content = (
        "You requested a password reset for AI Story.\n\n"
        f"Please open this link to reset your password:\n{reset_link}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this, you can ignore this email."
    )
    _send_email_via_runtime_smtp(to_email, "AI Story Password Reset", content)

