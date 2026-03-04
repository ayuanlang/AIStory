from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
import logging
import json
import random
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
    SystemAPISettingToggleDeprecatedRequest,
    SystemAPIProviderBatchDeprecatedRequest,
    SystemAPIProviderKeysUpdateRequest,
    SystemAPISettingImportRequest,
)
from app.api.deps import get_current_user
from typing import List, Dict, Tuple, Any

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


def _normalize_api_keys(values) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_items = values.replace("\r", "\n").replace(",", "\n").split("\n")
    elif isinstance(values, list):
        raw_items = values
    else:
        raw_items = [values]

    result: List[str] = []
    seen = set()
    for item in raw_items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _normalize_key_strategy(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"round_robin", "weighted", "random"}:
        return raw
    return "random"


def _normalize_key_weights(values, keys: List[str]) -> List[float]:
    if not keys:
        return []
    if values is None:
        return [1.0] * len(keys)
    raw_values = values if isinstance(values, list) else [values]
    parsed: List[float] = []
    for item in raw_values:
        try:
            val = float(item)
        except Exception:
            val = 1.0
        if val <= 0:
            val = 1.0
        parsed.append(val)

    if not parsed:
        parsed = [1.0]
    if len(parsed) < len(keys):
        parsed.extend([1.0] * (len(keys) - len(parsed)))
    return parsed[:len(keys)]


def _extract_provider_key_pool_from_row(row: SystemAPISetting) -> List[str]:
    cfg = _safe_json_dict(row.config)
    pooled = _normalize_api_keys(cfg.get("provider_api_keys"))
    if pooled:
        return pooled
    single = str(row.api_key or "").strip()
    return [single] if single else []


def _get_system_provider_key_pool(db: Session, provider: str) -> List[str]:
    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider).order_by(SystemAPISetting.id.asc()).all()
    merged: List[str] = []
    seen = set()
    for row in rows:
        for key in _extract_provider_key_pool_from_row(row):
            if key in seen:
                continue
            seen.add(key)
            merged.append(key)
    return merged


def _apply_system_provider_key_pool(db: Session, provider: str, keys: List[str]) -> None:
    normalized = _normalize_api_keys(keys)
    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider).all()
    primary_key = normalized[0] if normalized else ""
    for row in rows:
        cfg = _safe_json_dict(row.config)
        cfg["provider_api_keys"] = normalized
        strategy = _normalize_key_strategy(cfg.get("provider_api_key_strategy"))
        cfg["provider_api_key_strategy"] = strategy
        cfg["provider_api_key_weights"] = _normalize_key_weights(cfg.get("provider_api_key_weights"), normalized)
        row.config = cfg
        row.api_key = primary_key


def _pick_provider_runtime_key(config_value, fallback_key: str = "") -> str:
    cfg = _safe_json_dict(config_value)
    pooled = _normalize_api_keys(cfg.get("provider_api_keys"))
    if pooled:
        return random.choice(pooled)
    return str(fallback_key or "").strip()


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
    pool = _get_system_provider_key_pool(db, provider)
    if key and key not in pool:
        pool = [key, *pool]

    _apply_system_provider_key_pool(db, provider, pool)
    return pool[0] if pool else ""


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


def _is_setting_deprecated(config_value) -> bool:
    cfg = _safe_json_dict(config_value)
    return bool(
        cfg.get("deprecated")
        or cfg.get("is_deprecated")
        or cfg.get("disable_api")
    )


def _ensure_builtin_system_settings(db: Session) -> None:
    kie_base_url = "https://api.kie.ai"

    def _kie_item(name: str, category: str, model: str) -> Dict[str, Any]:
        return {
            "name": name,
            "category": category,
            "provider": "kie",
            "base_url": kie_base_url,
            "model": model,
            "config": {
                "endpoint": f"{kie_base_url}/api/v1/jobs/createTask",
                "query_endpoint": f"{kie_base_url}/api/v1/jobs/recordInfo",
                "credits_endpoint": f"{kie_base_url}/api/v1/user/credits",
                "deprecated": False,
            },
        }

    builtins = [
        _kie_item("Kie Z-image v4.0", "Image", "z-image-v4.0"),
        _kie_item("Kie Z-image v4.5", "Image", "z-image-v4.5"),
        _kie_item("Kie Grok Imagine", "Image", "grok-imagine"),
        _kie_item("Kie Flux-2", "Image", "flux-2"),
        _kie_item("Kie Google Imagen4 Fast", "Image", "imagen4-fast"),
        _kie_item("Kie Google Imagen4 Ultra", "Image", "imagen4-ultra"),
        _kie_item("Kie Ideogram", "Image", "ideogram"),
        _kie_item("Kie Qwen Image", "Image", "qwen-image"),
        _kie_item("Kie Recraft", "Image", "recraft"),
        _kie_item("Kie Topaz", "Image", "topaz"),

        _kie_item("Kie Kling v2.1", "Video", "kling-v2.1"),
        _kie_item("Kie Kling v2.5", "Video", "kling-v2.5"),
        _kie_item("Kie Sora2", "Video", "sora2"),
        _kie_item("Kie Bytedance v1 Pro", "Video", "bytedance-v1-pro"),
        _kie_item("Kie Bytedance v1 Lite", "Video", "bytedance-v1-lite"),
        _kie_item("Kie Hailuo", "Video", "hailuo"),
        _kie_item("Kie Wan Turbo", "Video", "wan-turbo"),
        _kie_item("Kie Grok Imagine Video", "Video", "grok-imagine-video"),

        _kie_item("Kie ElevenLabs", "Tools", "elevenlabs"),

        _kie_item("Kie Gemini 2.5 Flash", "LLM", "gemini-2.5-flash"),
        _kie_item("Kie Gemini 2.5 Pro", "LLM", "gemini-2.5-pro"),
    ]

    existing = db.query(SystemAPISetting.category, SystemAPISetting.provider, SystemAPISetting.model).filter(
        SystemAPISetting.provider == "kie"
    ).all()
    existing_keys = {
        ((c or "").strip().lower(), (p or "").strip().lower(), (m or "").strip().lower())
        for c, p, m in existing
    }

    to_create = []
    for item in builtins:
        key = (
            item["category"].strip().lower(),
            item["provider"].strip().lower(),
            item["model"].strip().lower(),
        )
        if key in existing_keys:
            continue
        to_create.append(item)

    if not to_create:
        return

    shared_key = ""
    key_row = db.query(SystemAPISetting.api_key).filter(
        SystemAPISetting.provider == "kie",
        SystemAPISetting.api_key.isnot(None),
        SystemAPISetting.api_key != "",
    ).order_by(SystemAPISetting.id.desc()).first()
    if key_row and (key_row[0] or "").strip():
        shared_key = key_row[0].strip()

    for item in to_create:
        db.add(SystemAPISetting(
            name=item["name"],
            category=item["category"],
            provider=item["provider"],
            api_key=shared_key,
            base_url=item["base_url"],
            model=item["model"],
            config=item["config"],
            is_active=False,
        ))

    db.flush()

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
    },
    "kie": {
        "category": "Video",
        "name": "KIE AI",
        "base_url": "https://api.kie.ai",
        "model": "veo3-fast",
        "config": {
            "endpoint": "https://api.kie.ai/api/v1/jobs/createTask",
            "query_endpoint": "https://api.kie.ai/api/v1/jobs/recordInfo"
        }
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

    _ensure_builtin_system_settings(db)

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

        key_pool = _normalize_api_keys((item_config or {}).get("provider_api_keys"))
        fallback_key = str(item.api_key or "").strip()
        runtime_key = key_pool[0] if key_pool else fallback_key
        has_key = bool(runtime_key)
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
                deprecated=_is_setting_deprecated(item_config),
                is_active=bool(user_is_active_for_row),
                has_api_key=has_key,
                api_key_masked=_mask_api_key(runtime_key) if has_key else "",
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

    _ensure_builtin_system_settings(db)
    db.commit()

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

    if _is_setting_deprecated(system_setting.config):
        raise HTTPException(status_code=400, detail="This system API setting is deprecated and cannot be activated")

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

    _ensure_builtin_system_settings(db)
    db.commit()

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


@router.post("/settings/system/manage/{setting_id}/deprecated", response_model=SystemAPISettingOut)
def toggle_system_setting_deprecated_for_manage(
    setting_id: int,
    payload: SystemAPISettingToggleDeprecatedRequest,
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

    cfg = _safe_json_dict(target.config)
    current = _is_setting_deprecated(cfg)
    next_value = (not current) if payload.deprecated is None else bool(payload.deprecated)

    cfg["deprecated"] = bool(next_value)
    # Keep legacy aliases aligned for compatibility.
    cfg["is_deprecated"] = bool(next_value)
    cfg["disable_api"] = bool(next_value)
    target.config = cfg

    db.commit()
    db.refresh(target)
    return target


@router.post("/settings/system/manage/provider/{provider}/deprecated")
def batch_toggle_system_provider_deprecated_for_manage(
    provider: str,
    payload: SystemAPIProviderBatchDeprecatedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    query = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name)
    category = str(payload.category or "").strip()
    if category:
        query = query.filter(SystemAPISetting.category == category)

    rows = query.order_by(SystemAPISetting.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No system API settings found for provider")

    changed = 0
    next_value = bool(payload.deprecated)
    for row in rows:
        cfg = _safe_json_dict(row.config)
        current = _is_setting_deprecated(cfg)
        if current != next_value:
            changed += 1
        cfg["deprecated"] = next_value
        cfg["is_deprecated"] = next_value
        cfg["disable_api"] = next_value
        row.config = cfg

    db.commit()

    return {
        "ok": True,
        "provider": provider_name,
        "category": category or None,
        "deprecated": next_value,
        "matched": len(rows),
        "changed": changed,
    }


@router.get("/settings/system/manage/provider/{provider}/keys")
def get_system_provider_keys_for_manage(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    pool = _get_system_provider_key_pool(db, provider_name)
    first_row = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name).order_by(SystemAPISetting.id.asc()).first()
    cfg = _safe_json_dict(first_row.config if first_row else {})
    strategy = _normalize_key_strategy(cfg.get("provider_api_key_strategy"))
    weights = _normalize_key_weights(cfg.get("provider_api_key_weights"), pool)
    return {
        "provider": provider_name,
        "key_count": len(pool),
        "keys": pool,
        "keys_masked": [_mask_api_key(k) for k in pool],
        "strategy": strategy,
        "weights": weights,
    }


@router.post("/settings/system/manage/provider/{provider}/keys")
def set_system_provider_keys_for_manage(
    provider: str,
    payload: SystemAPIProviderKeysUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No system API settings found for provider")

    pool = _normalize_api_keys(payload.keys)
    strategy = _normalize_key_strategy(payload.strategy)
    weights = _normalize_key_weights(payload.weights, pool)

    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name).all()
    primary_key = pool[0] if pool else ""
    for row in rows:
        cfg = _safe_json_dict(row.config)
        cfg["provider_api_keys"] = pool
        cfg["provider_api_key_strategy"] = strategy
        cfg["provider_api_key_weights"] = weights
        row.config = cfg
        row.api_key = primary_key
    db.commit()

    return {
        "ok": True,
        "provider": provider_name,
        "key_count": len(pool),
        "keys_masked": [_mask_api_key(k) for k in pool],
        "strategy": strategy,
        "weights": weights,
    }


@router.get("/settings/system/manage/export")
def export_system_settings_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_builtin_system_settings(db)
    db.commit()

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
