# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.admin_ops_pkg import shared as _shared

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


# --- admin configs ---
@router.get("/admin/payment-config", response_model=PaymentConfig)
def get_payment_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    setting = _get_active_wechat_config(db)
    if not setting:
        return PaymentConfig()

    return PaymentConfig(
        mchid=str(setting.mchid or ""),
        appid=str(setting.appid or ""),
        api_v3_key=str(setting.api_v3_key or ""),
        cert_serial_no=str(setting.cert_serial_no or ""),
        private_key=str(setting.private_key or ""),
        notify_url=str(setting.notify_url or ""),
        use_mock=bool(setting.use_mock),
    )

@router.post("/admin/payment-config", response_model=PaymentConfig)
def update_payment_config(
    idx: PaymentConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    setting = _get_active_wechat_config(db)
    
    if not setting:
        setting = WechatPayConfig(
            is_active=True,
            created_at=now_bj_iso(),
            updated_at=now_bj_iso(),
        )
        db.add(setting)

    setting.mchid = str(idx.mchid or "").strip()
    setting.appid = str(idx.appid or "").strip()
    setting.api_v3_key = str(idx.api_v3_key or "").strip()
    setting.cert_serial_no = str(idx.cert_serial_no or "").strip()
    setting.private_key = str(idx.private_key or "")
    setting.notify_url = str(idx.notify_url or "").strip()
    setting.use_mock = bool(idx.use_mock)
    setting.updated_at = now_bj_iso()
    
    db.commit()
    db.refresh(setting)
    
    # Update Service Immediately
    payment_service.update_config({
        "mchid": idx.mchid,
        "appid": idx.appid,
        "api_v3_key": idx.api_v3_key,
        "cert_serial_no": idx.cert_serial_no,
        "private_key": idx.private_key,
        "notify_url": idx.notify_url,
        "use_mock": idx.use_mock
    })
    
    return idx


@router.get("/admin/smtp-config", response_model=SMTPConfig)
def get_smtp_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not inspect(db.connection()).has_table("smtp_system_configs"):
        return SMTPConfig(
            host=str(settings.SMTP_HOST or "").strip(),
            port=int(settings.SMTP_PORT or 587),
            username=str(settings.SMTP_USERNAME or "").strip(),
            password="",
            use_ssl=os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
            use_tls=bool(settings.SMTP_USE_TLS),
            from_email=str(settings.SMTP_FROM_EMAIL or "").strip(),
            frontend_base_url=str(settings.FRONTEND_BASE_URL or "").strip(),
        )

    setting = db.query(SMTPSystemConfig).filter(
        SMTPSystemConfig.is_active == True,
    ).order_by(SMTPSystemConfig.id.desc()).first()

    if not setting:
        return SMTPConfig(
            host=str(settings.SMTP_HOST or "").strip(),
            port=int(settings.SMTP_PORT or 587),
            username=str(settings.SMTP_USERNAME or "").strip(),
            password="",
            use_ssl=os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
            use_tls=bool(settings.SMTP_USE_TLS),
            from_email=str(settings.SMTP_FROM_EMAIL or "").strip(),
            frontend_base_url=str(settings.FRONTEND_BASE_URL or "").strip(),
        )

    return SMTPConfig(
        host=str(setting.host or "").strip(),
        port=int(setting.port or 587),
        username=str(setting.username or "").strip(),
        password=str(setting.password or ""),
        use_ssl=bool(setting.use_ssl),
        use_tls=bool(setting.use_tls),
        from_email=str(setting.from_email or "").strip(),
        frontend_base_url=str(setting.frontend_base_url or "").strip(),
    )


@router.post("/admin/smtp-config", response_model=SMTPConfig)
def update_smtp_config(
    idx: SMTPConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not inspect(db.connection()).has_table("smtp_system_configs"):
        SMTPSystemConfig.__table__.create(bind=db.get_bind(), checkfirst=True)

    setting = db.query(SMTPSystemConfig).filter(
        SMTPSystemConfig.is_active == True,
    ).order_by(SMTPSystemConfig.id.desc()).first()

    if not setting:
        setting = SMTPSystemConfig(
            is_active=True,
            created_at=now_bj_iso(),
            updated_at=now_bj_iso(),
        )
        db.add(setting)

    setting.host = str(idx.host or "").strip()
    setting.port = int(idx.port or 587)
    setting.username = str(idx.username or "").strip()
    setting.password = str(idx.password or "")
    setting.use_ssl = bool(idx.use_ssl)
    setting.use_tls = bool(idx.use_tls)
    setting.from_email = str(idx.from_email or "").strip()
    setting.frontend_base_url = str(idx.frontend_base_url or "").strip()
    setting.updated_at = now_bj_iso()

    db.commit()
    db.refresh(setting)
    return idx


@router.post("/admin/smtp-config/test")
def test_smtp_config(
    payload: SMTPTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    del db
    target_email = str(payload.to_email or "").strip()
    if not target_email:
        raise HTTPException(status_code=400, detail="测试邮箱不能为空")

    subject = "AI Story SMTP 测试邮件"
    content = (
        "这是一封来自 AI Story 的 SMTP 测试邮件。\n\n"
        "如果你收到了这封邮件，说明 SMTP 配置可用。"
    )

    try:
        _send_email_via_runtime_smtp(target_email, subject, content, strict=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"发送失败：{exc}")

    return {"success": True, "message": f"测试邮件已发送到 {target_email}"}


@router.post("/admin/smtp-config/broadcast")
def broadcast_email_to_all_users(
    payload: SMTPBroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if str(payload.confirm_phrase or "").strip() != "SEND_TO_ALL_USERS":
        raise HTTPException(status_code=400, detail="确认口令错误，请输入 SEND_TO_ALL_USERS")

    subject = str(payload.subject or "").strip()
    html_content = str(payload.content_html or "")
    text_content = str(payload.content_text or "").strip()

    if not subject:
        raise HTTPException(status_code=400, detail="邮件主题不能为空")

    if not html_content.strip() and not text_content:
        raise HTTPException(status_code=400, detail="邮件内容不能为空（HTML 或文本至少填写一个）")

    if not text_content:
        text_content = "This email contains HTML content. Please view it in an HTML-compatible email client."

    rows = db.query(User.email).all()
    raw_emails = [str((row[0] or "")).strip().lower() for row in rows]

    recipients = []
    invalid_count = 0
    seen = set()
    for email in raw_emails:
        if not email:
            continue
        if email in seen:
            continue
        seen.add(email)
        if _is_valid_email_format(email):
            recipients.append(email)
        else:
            invalid_count += 1

    if not recipients:
        raise HTTPException(status_code=400, detail="没有可用的收件邮箱")

    sent = 0
    failed = 0
    errors = []
    for email in recipients:
        try:
            _send_email_via_runtime_smtp(
                email,
                subject,
                text_content,
                html_content=html_content,
                strict=True,
            )
            sent += 1
        except Exception as exc:
            failed += 1
            if len(errors) < 10:
                errors.append({"email": email, "error": str(exc)})

    return {
        "success": failed == 0,
        "total": len(recipients),
        "sent": sent,
        "failed": failed,
        "invalid": invalid_count,
        "errors": errors,
    }


@router.get("/admin/maintenance-status", response_model=MaintenanceStatusOut)
def get_maintenance_status(db: Session = Depends(get_db)):
    status = _resolve_maintenance_config_raw(db)
    return MaintenanceStatusOut(**status)


@router.get("/admin/maintenance-config", response_model=MaintenanceConfig)
def get_maintenance_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    status = _resolve_maintenance_config_raw(db)
    return MaintenanceConfig(
        enabled=bool(status.get("enabled")),
        ends_at=status.get("ends_at"),
        message=status.get("message") or "系统正在维护",
    )


@router.post("/admin/maintenance-config", response_model=MaintenanceConfig)
def update_maintenance_config(
    idx: MaintenanceConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    row = db.execute(text("""
        SELECT id
        FROM system_api_settings
        WHERE category = :category
          AND provider = :provider
        ORDER BY id DESC
        LIMIT 1
    """), {
        "category": _MAINTENANCE_CATEGORY,
        "provider": _MAINTENANCE_PROVIDER,
    }).mappings().first()

    ends_at = str(idx.ends_at or "").strip()
    if ends_at and not _parse_iso_datetime_safe(ends_at):
        raise HTTPException(status_code=400, detail="ends_at must be a valid ISO datetime")

    next_config = {
        "enabled": bool(idx.enabled),
        "ends_at": ends_at or None,
        "message": str(idx.message or "系统正在维护").strip() or "系统正在维护",
    }

    if row and row.get("id") is not None:
        db.execute(text("""
            UPDATE system_api_settings
            SET config = :config
            WHERE id = :id
        """), {
            "id": int(row["id"]),
            "config": next_config,
        })
    else:
        db.execute(text("""
            INSERT INTO system_api_settings (
                category,
                provider,
                name,
                model,
                is_active,
                config
            ) VALUES (
                :category,
                :provider,
                :name,
                :model,
                :is_active,
                :config
            )
        """), {
            "category": _MAINTENANCE_CATEGORY,
            "provider": _MAINTENANCE_PROVIDER,
            "name": "System Maintenance Config",
            "model": "maintenance_mode_config",
            "is_active": True,
            "config": next_config,
        })

    db.commit()
    _store_login_maintenance_cache(
        _build_maintenance_status_payload(next_config),
        read_failed=False,
    )

    return MaintenanceConfig(
        enabled=bool(next_config.get("enabled", False)),
        ends_at=next_config.get("ends_at"),
        message=next_config.get("message") or "系统正在维护",
    )



