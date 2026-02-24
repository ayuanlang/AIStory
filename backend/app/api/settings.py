from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
import logging
import json
from datetime import datetime
from app.db.session import get_db
from app.models.all_models import APISetting, User, PricingRule, SystemAPISetting
from app.schemas.settings import (
    APISettingOut,
    APISettingUpdate,
    SystemAPIModelOption,
    SystemAPIProviderModelCatalog,
    SystemAPIProviderSettings,
    SystemAPISettingOut,
    SystemAPISelectionRequest,
    SystemAPISettingManageCreate,
    SystemAPISettingManageUpdate,
    SystemAPISettingImportRequest,
)
from app.api.deps import get_current_user
from typing import List, Dict, Tuple

router = APIRouter()
logger = logging.getLogger("settings_api")


def _mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}***{api_key[-4:]}"


def _safe_json_dict(value) -> Dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _can_use_system_settings(user: User) -> bool:
    return bool(user and user.is_active)


def _can_manage_system_settings(user: User) -> bool:
    return bool(user.is_superuser)


def _ensure_default_system_selection_for_user(db: Session, user_id: int) -> None:
    existing_count = db.query(APISetting).filter(APISetting.user_id == user_id).count()
    if existing_count > 0:
        return

    active_system_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.is_active == True,
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.id.desc()).all()

    if not active_system_rows:
        return

    selected_by_category: Dict[str, SystemAPISetting] = {}
    for row in active_system_rows:
        category = str(row.category or "").strip()
        if not category or category in selected_by_category:
            continue
        selected_by_category[category] = row

    for _, system_setting in selected_by_category.items():
        marker_config = dict(system_setting.config or {})
        marker_config["selection_source"] = "system"

        db.add(APISetting(
            user_id=user_id,
            name=f"Use System {system_setting.provider}",
            category=system_setting.category,
            provider=system_setting.provider,
            api_key="",
            base_url=system_setting.base_url,
            model=system_setting.model,
            config=marker_config,
            is_active=True,
        ))

    db.flush()


def _sync_provider_shared_key(db: Session, user_id: int, provider: str, current_setting_id: int, incoming_api_key: str = None) -> str:
    if not provider:
        return incoming_api_key or ""

    key = (incoming_api_key or "").strip()
    provider_settings = db.query(APISetting).filter(
        APISetting.user_id == user_id,
        APISetting.provider == provider,
    ).all()

    if key:
        for item in provider_settings:
            if item.id != current_setting_id:
                item.api_key = key
        return key

    # No incoming key: inherit existing provider key (shared by provider)
    for item in provider_settings:
        if item.id != current_setting_id and (item.api_key or "").strip():
            return item.api_key
    return ""


def _sync_system_provider_shared_key(db: Session, provider: str, current_setting_id: int, incoming_api_key: str = None) -> str:
    if not provider:
        return incoming_api_key or ""

    key = (incoming_api_key or "").strip()
    provider_settings = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == provider,
    ).all()

    if key:
        for item in provider_settings:
            if item.id != current_setting_id:
                item.api_key = key
        return key

    for item in provider_settings:
        if item.id != current_setting_id and (item.api_key or "").strip():
            return item.api_key
    return ""


def _task_type_to_category(task_type: str) -> str:
    task = (task_type or "").strip().lower()
    if task == "image_gen":
        return "Image"
    if task == "video_gen":
        return "Video"
    if task == "analysis":
        return "Vision"
    if task == "llm_chat":
        return "LLM"
    return "Tools"

DEFAULTS = {
    "openai": {
        "category": "LLM",
        "name": "OpenAI Default",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4-turbo-preview",
        "config": {"temperature": 0.7}
    },
    "anthropic": {
        "category": "LLM",
        "name": "Anthropic Default",
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-opus-20240229",
        "config": {"max_tokens": 1024}
    },
    "baidu": {
        "category": "LLM",
        "name": "Baidu Ernie",
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "model": "completions_pro",
        "config": {}
    },
    "stability": {
        "category": "Image",
        "name": "Stability Core",
        "base_url": "https://api.stability.ai",
        "model": "stable-diffusion-xl-1024-v1-0",
        "config": {"steps": 30}
    },
    "runway": {
        "category": "Video",
        "name": "Runway Gen-2",
        "base_url": "https://api.runwayml.com",
        "model": "gen-2",
        "config": {}
    },
    "elevenlabs": {
        "category": "Voice",
        "name": "ElevenLabs v1",
        "base_url": "https://api.elevenlabs.io/v1",
        "model": "premade/Adam",
        "config": {}
    },
    "ark": {
        "category": "LLM", 
        "name": "Volcengine Ark", 
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
        "config": {}
    },
    "grsai": {
        "category": "Video",
        "name": "Grsai (Sora)",
        "base_url": "https://grsai.dakka.com.cn",
        "model": "sora-image", 
        "config": {}
    },
    "tencent": {
        "category": "Image",
        "name": "Tencent Hunyuan",
        "base_url": "https://aiart.tencentcloudapi.com",
        "model": "hunyuan-vision",
        "config": {}
    },
    "wanxiang": {
        "category": "Video",
        "name": "Aliyun Wanxiang",
        "base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis",
        "model": "wanx2.1-kf2v-plus",
        "config": {}
    }
}

@router.get("/settings", response_model=List[APISettingOut])
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_default_system_selection_for_user(db, current_user.id)
    db.commit()
    settings = db.query(APISetting).filter(APISetting.user_id == current_user.id).all()
    return settings

@router.post("/settings", response_model=APISettingOut)
def update_setting(
    setting_in: APISettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    # Identify Category
    provider = setting_in.provider
    default_info = DEFAULTS.get(provider, {})
    category = setting_in.category or default_info.get("category", "LLM")
    
    # If this request is setting item to Active, we must deactivate others in same category
    if setting_in.is_active:
        existing_active = db.query(APISetting).filter(
            APISetting.user_id == current_user.id,
            APISetting.category == category,
            APISetting.is_active == True
        ).all()
        for s in existing_active:
            s.is_active = False
            
    # Check if we are updating an existing ID
    if setting_in.id:
        db_setting = db.query(APISetting).filter(APISetting.id == setting_in.id, APISetting.user_id == current_user.id).first()
        if not db_setting:
            raise HTTPException(status_code=404, detail="Setting not found")
            
        # Update fields
        # Loop through fields in schema but skip None
        update_data = setting_in.dict(exclude_unset=True)
        for key, value in update_data.items():
            if key != 'id':
                setattr(db_setting, key, value)
                
        # Ensure category is set if missing
        if not db_setting.category:
            db_setting.category = category

        if not db_setting.provider and provider:
            db_setting.provider = provider
            
    else:
        # Create New
        if not provider:
            raise HTTPException(status_code=400, detail="provider is required when creating a setting")

        new_setting = APISetting(
            user_id=current_user.id,
            name=setting_in.name or default_info.get("name", provider),
            category=category,
            provider=provider,
            api_key=setting_in.api_key or "",
            base_url=setting_in.base_url or default_info.get("base_url"),
            model=setting_in.model or default_info.get("model"),
            config=setting_in.config or default_info.get("config"),
            is_active=setting_in.is_active
        )
        db.add(new_setting)
        db_setting = new_setting

    # Provider-level shared key strategy:
    # Same user + same provider should share one API key across multiple model rows.
    effective_provider = db_setting.provider
    effective_key = _sync_provider_shared_key(
        db,
        current_user.id,
        effective_provider,
        db_setting.id or -1,
        setting_in.api_key,
    )
    db_setting.api_key = effective_key

    db.commit()
    db.refresh(db_setting)
    return db_setting


@router.get("/settings/system", response_model=List[SystemAPIProviderSettings])
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_use_system_settings(current_user):
        return []

    _ensure_default_system_selection_for_user(db, current_user.id)
    db.commit()

    system_settings = db.query(
        SystemAPISetting.id,
        SystemAPISetting.name,
        SystemAPISetting.provider,
        SystemAPISetting.category,
        SystemAPISetting.model,
        SystemAPISetting.base_url,
        SystemAPISetting.api_key,
        cast(SystemAPISetting.config, String).label("config_raw"),
    ).filter(
        SystemAPISetting.category != "System_Payment"
    ).all()

    # Build user's active map (one active per category should be maintained).
    user_active_by_category: Dict[str, Dict] = {}
    user_active_rows = db.query(
        APISetting.id,
        APISetting.category,
        APISetting.provider,
        APISetting.model,
        cast(APISetting.config, String).label("config_raw"),
    ).filter(
        APISetting.user_id == current_user.id,
        APISetting.is_active == True,
    ).all()
    for row in user_active_rows:
        cat = row.category or "LLM"
        row_data = {
            "id": row.id,
            "category": row.category,
            "provider": row.provider,
            "model": row.model,
            "config": _safe_json_dict(getattr(row, "config_raw", None)),
        }
        # Keep latest id if historical duplicates exist.
        if cat not in user_active_by_category or (row.id or 0) > (user_active_by_category[cat].get("id") or 0):
            user_active_by_category[cat] = row_data

    grouped: Dict[Tuple[str, str], Dict] = {}
    for item in system_settings:
        provider = item.provider or "unknown"
        category = item.category or "LLM"
        item_config = _safe_json_dict(getattr(item, "config_raw", None))
        if getattr(item, "config_raw", None) and not item_config:
            logger.warning(
                "Invalid JSON in system setting config, fallback to empty dict | setting_id=%s provider=%s category=%s",
                item.id,
                provider,
                category,
            )
        key = (provider, category)
        if key not in grouped:
            grouped[key] = {
                "provider": provider,
                "category": category,
                "shared_key_configured": False,
                "models": [],
            }

        has_key = bool((item.api_key or "").strip())
        grouped[key]["shared_key_configured"] = grouped[key]["shared_key_configured"] or has_key

        user_active = user_active_by_category.get(category)
        user_is_active_for_row = False
        if user_active:
            user_is_active_for_row = (
                (user_active.get("provider") == item.provider)
                and ((user_active.get("model") or "") == (item.model or ""))
            )

        grouped[key]["models"].append(
            SystemAPIModelOption(
                id=item.id,
                name=item.name,
                provider=provider,
                category=category,
                model=item.model,
                base_url=item.base_url,
                webhook_url=(item_config or {}).get("webHook"),
                is_active=bool(user_is_active_for_row),
                has_api_key=has_key,
                api_key_masked=_mask_api_key(item.api_key or "") if has_key else "",
            )
        )

    result = []
    for _, row in grouped.items():
        row["models"] = sorted(row["models"], key=lambda m: (m.model or "", m.id))
        result.append(SystemAPIProviderSettings(**row))

    return sorted(result, key=lambda r: (r.category, r.provider))


@router.get("/settings/system/catalog", response_model=List[SystemAPIProviderModelCatalog])
def get_system_settings_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_use_system_settings(current_user) and not _can_manage_system_settings(current_user):
        return []

    grouped: Dict[Tuple[str, str], set] = {}

    pricing_rows = db.query(PricingRule.provider, PricingRule.model, PricingRule.task_type).all()
    for provider, model, task_type in pricing_rows:
        provider_name = (provider or "").strip()
        if not provider_name:
            continue
        category = _task_type_to_category(task_type)
        key = (category, provider_name)
        if key not in grouped:
            grouped[key] = set()
        if (model or "").strip():
            grouped[key].add(model.strip())

    setting_rows = db.query(SystemAPISetting.provider, SystemAPISetting.model, SystemAPISetting.category).filter(
        SystemAPISetting.provider.isnot(None)
    ).all()
    for provider, model, category in setting_rows:
        provider_name = (provider or "").strip()
        if not provider_name:
            continue
        cat = (category or "Tools").strip() or "Tools"
        key = (cat, provider_name)
        if key not in grouped:
            grouped[key] = set()
        if (model or "").strip():
            grouped[key].add(model.strip())

    result = [
        SystemAPIProviderModelCatalog(
            category=category,
            provider=provider,
            models=sorted(models),
        )
        for (category, provider), models in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
    ]
    return result


@router.post("/settings/system/select", response_model=APISettingOut)
def select_system_setting(
    selection: SystemAPISelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    system_setting = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == selection.setting_id,
    ).first()
    if not system_setting:
        raise HTTPException(status_code=404, detail="System API setting not found")

    # Enforce one-active-per-category for current user.
    db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.category == system_setting.category,
        APISetting.is_active == True,
    ).update({"is_active": False})

    user_setting = db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.provider == system_setting.provider,
        APISetting.category == system_setting.category,
        APISetting.model == system_setting.model,
    ).first()

    marker_config = dict(system_setting.config or {})
    marker_config["selection_source"] = "system"

    if user_setting:
        user_setting.name = user_setting.name or f"Use System {system_setting.provider}"
        user_setting.base_url = system_setting.base_url
        user_setting.model = system_setting.model
        user_setting.config = marker_config
        user_setting.is_active = True
        # Keep API key empty to force runtime lookup from system-side key.
        user_setting.api_key = ""
        selected = user_setting
    else:
        selected = APISetting(
            user_id=current_user.id,
            name=f"Use System {system_setting.provider}",
            category=system_setting.category,
            provider=system_setting.provider,
            api_key="",
            base_url=system_setting.base_url,
            model=system_setting.model,
            config=marker_config,
            is_active=True,
        )
        db.add(selected)

    db.commit()
    db.refresh(selected)
    return selected


@router.get("/settings/system/manage", response_model=List[SystemAPISettingOut])
def list_system_settings_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.provider.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()
    return rows


@router.post("/settings/system/manage", response_model=SystemAPISettingOut)
def create_system_setting_for_manage(
    payload: SystemAPISettingManageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider = (payload.provider or "").strip()
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")

    category = (payload.category or "LLM").strip() or "LLM"
    create_config = payload.config if isinstance(payload.config, dict) else {}
    new_setting = SystemAPISetting(
        name=(payload.name or "System Setting").strip() or "System Setting",
        category=category,
        provider=provider,
        api_key="",
        base_url=payload.base_url,
        model=payload.model,
        config=create_config,
        is_active=bool(payload.is_active),
    )
    db.add(new_setting)
    db.flush()

    # Keep provider-level key shared across all system rows for the same provider.
    effective_key = _sync_system_provider_shared_key(
        db,
        new_setting.provider,
        new_setting.id,
        payload.api_key,
    )
    new_setting.api_key = effective_key

    if new_setting.is_active:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == new_setting.category,
            SystemAPISetting.id != new_setting.id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False})

    db.commit()
    db.refresh(new_setting)
    return new_setting


@router.post("/settings/system/manage/{setting_id}", response_model=SystemAPISettingOut)
def update_system_setting_for_manage(
    setting_id: int,
    payload: SystemAPISettingManageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == setting_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target, key, value)

    if payload.is_active:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == target.category,
            SystemAPISetting.id != target.id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False})

    # Keep provider-level key shared among system rows as well.
    effective_key = _sync_system_provider_shared_key(
        db,
        target.provider,
        target.id,
        payload.api_key,
    )
    target.api_key = effective_key

    db.commit()
    db.refresh(target)
    return target


@router.get("/settings/system/manage/export")
def export_system_settings_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.provider.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()

    return {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "count": len(rows),
        "items": [
            {
                "name": row.name,
                "category": row.category,
                "provider": row.provider,
                "api_key": row.api_key,
                "base_url": row.base_url,
                "model": row.model,
                "config": row.config or {},
                "is_active": bool(row.is_active),
            }
            for row in rows
        ],
    }


@router.post("/settings/system/manage/import")
def import_system_settings_for_manage(
    payload: SystemAPISettingImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    items = payload.items or []
    if not items:
        return {"ok": True, "created": 0, "updated": 0, "total": 0}

    if payload.replace_all:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category != "System_Payment",
        ).delete(synchronize_session=False)
        db.flush()

    created = 0
    updated = 0
    last_active_id_by_category: Dict[str, int] = {}

    for item in items:
        provider = (item.provider or "").strip()
        category = (item.category or "LLM").strip() or "LLM"
        model = (item.model or "").strip()
        if not provider:
            continue

        target = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.provider == provider,
            SystemAPISetting.model == model,
        ).order_by(SystemAPISetting.id.desc()).first()

        if target:
            target.name = (item.name or target.name or "System Setting").strip() or "System Setting"
            target.base_url = item.base_url
            target.model = item.model
            target.config = item.config if isinstance(item.config, dict) else {}
            target.is_active = bool(item.is_active)
            updated += 1
        else:
            target = SystemAPISetting(
                name=(item.name or "System Setting").strip() or "System Setting",
                category=category,
                provider=provider,
                api_key="",
                base_url=item.base_url,
                model=item.model,
                config=item.config if isinstance(item.config, dict) else {},
                is_active=bool(item.is_active),
            )
            db.add(target)
            db.flush()
            created += 1

        effective_key = _sync_system_provider_shared_key(
            db,
            target.provider,
            target.id,
            item.api_key,
        )
        target.api_key = effective_key

        if bool(item.is_active):
            last_active_id_by_category[category] = target.id

    for category, keep_id in last_active_id_by_category.items():
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.id != keep_id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False}, synchronize_session=False)

    db.commit()
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "total": created + updated,
    }


@router.delete("/settings/system/manage/{setting_id}")
def delete_system_setting_for_manage(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == setting_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    db.delete(target)
    db.commit()
    return {"ok": True}

@router.delete("/settings/{setting_id}")
def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(APISetting).filter(APISetting.id == setting_id, APISetting.user_id == current_user.id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
        
    db.delete(setting)
    db.commit()
    return {"ok": True}

@router.get("/settings/defaults")
def get_defaults():
    return DEFAULTS
