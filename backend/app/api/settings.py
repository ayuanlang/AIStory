from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import APISetting, User
from app.schemas.settings import (
    APISettingOut,
    APISettingUpdate,
    SystemAPIModelOption,
    SystemAPIProviderSettings,
    SystemAPISelectionRequest,
    SystemAPISettingManageCreate,
    SystemAPISettingManageUpdate,
)
from app.api.deps import get_current_user
from typing import List, Dict, Tuple

router = APIRouter()


def _mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}***{api_key[-4:]}"


def _can_use_system_settings(user: User) -> bool:
    return bool((user.credits or 0) > 0 or user.is_superuser or user.is_system)


def _can_manage_system_settings(user: User) -> bool:
    return bool(user.is_superuser or user.is_system)


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

    system_settings = db.query(APISetting).join(User, APISetting.user_id == User.id).filter(
        User.is_system == True,
        APISetting.category != "System_Payment"
    ).all()

    # Build user's active map (one active per category should be maintained).
    user_active_by_category: Dict[str, APISetting] = {}
    user_active_rows = db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.is_active == True,
    ).all()
    for row in user_active_rows:
        cat = row.category or "LLM"
        # Keep latest id if historical duplicates exist.
        if cat not in user_active_by_category or (row.id or 0) > (user_active_by_category[cat].id or 0):
            user_active_by_category[cat] = row

    grouped: Dict[Tuple[str, str], Dict] = {}
    for item in system_settings:
        provider = item.provider or "unknown"
        category = item.category or "LLM"
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
        user_selected_system_id = ((user_active.config or {}).get("use_system_setting_id") if user_active else None)
        user_is_active_for_row = False
        if user_selected_system_id:
            user_is_active_for_row = int(user_selected_system_id) == int(item.id)
        elif user_active:
            user_is_active_for_row = (
                (user_active.provider == item.provider)
                and ((user_active.model or "") == (item.model or ""))
            )

        grouped[key]["models"].append(
            SystemAPIModelOption(
                id=item.id,
                name=item.name,
                user_id=item.user_id,
                provider=provider,
                category=category,
                model=item.model,
                base_url=item.base_url,
                webhook_url=(item.config or {}).get("webHook"),
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


@router.post("/settings/system/select", response_model=APISettingOut)
def select_system_setting(
    selection: SystemAPISelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_use_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Insufficient credits to use system API settings")

    system_setting = db.query(APISetting).join(User, APISetting.user_id == User.id).filter(
        APISetting.id == selection.setting_id,
        User.is_system == True,
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
    marker_config["use_system_setting_id"] = system_setting.id
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


@router.get("/settings/system/manage", response_model=List[APISettingOut])
def list_system_settings_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    rows = db.query(APISetting).join(User, APISetting.user_id == User.id).filter(
        User.is_system == True,
        APISetting.category != "System_Payment",
    ).order_by(APISetting.category.asc(), APISetting.provider.asc(), APISetting.model.asc(), APISetting.id.asc()).all()
    return rows


@router.post("/settings/system/manage", response_model=APISettingOut)
def create_system_setting_for_manage(
    payload: SystemAPISettingManageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    system_owner_id = current_user.id
    if not current_user.is_system:
        system_owner = db.query(User).filter(User.is_system == True).order_by(User.id.asc()).first()
        if not system_owner:
            raise HTTPException(status_code=400, detail="No system user found to own system API settings")
        system_owner_id = system_owner.id

    provider = (payload.provider or "").strip()
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")

    category = (payload.category or "LLM").strip() or "LLM"
    create_config = payload.config if isinstance(payload.config, dict) else {}
    new_setting = APISetting(
        user_id=system_owner_id,
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
    effective_key = _sync_provider_shared_key(
        db,
        new_setting.user_id,
        new_setting.provider,
        new_setting.id,
        payload.api_key,
    )
    new_setting.api_key = effective_key

    if new_setting.is_active:
        db.query(APISetting).filter(
            APISetting.user_id == new_setting.user_id,
            APISetting.category == new_setting.category,
            APISetting.id != new_setting.id,
            APISetting.is_active == True,
        ).update({"is_active": False})

    db.commit()
    db.refresh(new_setting)
    return new_setting


@router.post("/settings/system/manage/{setting_id}", response_model=APISettingOut)
def update_system_setting_for_manage(
    setting_id: int,
    payload: SystemAPISettingManageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(APISetting).join(User, APISetting.user_id == User.id).filter(
        APISetting.id == setting_id,
        User.is_system == True,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target, key, value)

    if payload.is_active:
        db.query(APISetting).filter(
            APISetting.user_id == target.user_id,
            APISetting.category == target.category,
            APISetting.id != target.id,
            APISetting.is_active == True,
        ).update({"is_active": False})

    # Keep provider-level key shared among system rows as well.
    effective_key = _sync_provider_shared_key(
        db,
        target.user_id,
        target.provider,
        target.id,
        payload.api_key,
    )
    target.api_key = effective_key

    db.commit()
    db.refresh(target)
    return target

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
