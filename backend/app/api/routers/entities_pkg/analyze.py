# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.entities_pkg import shared as _shared

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


# --- entity analyze/history ---
@router.post("/entities/{entity_id}/analyze")
async def analyze_entity_image(
    entity_id: int,
    background_tasks: BackgroundTasks,
    system_api_id: Optional[int] = Query(None),
    feature_name: Optional[str] = Query(None),
    bg: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an entity (subject) image using Vision model and updates its attributes based on visual content.
    Returns the updated entity data.
    """
    if not bg:
        return await _execute_analyze_entity_image(entity_id, system_api_id, feature_name, db, current_user)
        
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    # verify access
    project = _require_project_access(db, entity.project_id, current_user)

    if not entity.image_url:
        raise HTTPException(status_code=400, detail="Entity has no image to analyze.")

    async def bg_task(u_id: int):
        from app.db.session import SessionLocal
        with SessionLocal() as bg_db:
            try:
                u = bg_db.query(User).filter(User.id == u_id).first()
                if u:
                    await _execute_analyze_entity_image(entity_id, system_api_id, feature_name, bg_db, u)
            except Exception as e:
                logger.error(f"BG Analyze task failed for entity {entity_id}: {e}")

    background_tasks.add_task(bg_task, current_user.id)
    return entity


def _entity_analysis_parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, (dict, list)) else {}
    except Exception:
        return {}


def _entity_analysis_category(entity_type: Any) -> str:
    raw = str(entity_type or "character").strip().lower()
    if "prop" in raw or "item" in raw or "物件" in raw or "道具" in raw:
        return "prop"
    if "poster" in raw or "cover" in raw or "海报" in raw or "封面" in raw:
        return "poster"
    if "env" in raw or "scene" in raw or "场景" in raw or "环境" in raw:
        return "environment"
    return "character"


def _entity_analysis_is_main_environment(entity: Any) -> bool:
    """Detect Stage-3 main/baseline environment (四向拼图 / 2x2), vs derivative ENV."""
    dep_raw = _entity_analysis_parse_jsonish(getattr(entity, "dependency_strategy", None))
    dep = dep_raw if isinstance(dep_raw, dict) else {}
    dep_type = str(dep.get("type") or "").strip()
    if dep_type == "BaselineDefinition":
        return True

    name = str(getattr(entity, "name", "") or "").strip()
    prompt_cn = str(getattr(entity, "generation_prompt_cn", "") or "")
    desc_cn = str(getattr(entity, "description", "") or getattr(entity, "description_cn", "") or "")
    joined = f"{prompt_cn}\n{desc_cn}"

    # Angle / state derivatives are never main baseline.
    if re.match(r"^\d+\s*度", name) or re.search(r"(^|[_\s])\d+\s*度", name):
        return False
    if any(marker in joined for marker in ("§A", "§B", "§C", "参考图为", "本镜头 Delta", "本镜 Delta")):
        return False
    if any(
        marker in joined
        for marker in (
            "四向拼图",
            "2×2",
            "2x2",
            "四宫格",
            "[0度格",
            "左上=0度",
            "左上＝0度",
            "BaselineDefinition",
        )
    ):
        return True

    deps_raw = _entity_analysis_parse_jsonish(getattr(entity, "visual_dependencies", None))
    deps = deps_raw if isinstance(deps_raw, list) else []
    has_env_dep = any(
        str(item or "").strip().upper().startswith("ENV:")
        or str(item or "").strip().startswith("ENV：[")
        or str(item or "").strip().startswith("ENV:[")
        for item in deps
    )
    if has_env_dep:
        return False
    # No ENV dependency and no derivative markers → treat as main/baseline.
    return dep_type in ("", "Original", "BaselineDefinition")


def _build_entity_analysis_format_contract(entity: Any, category: str) -> str:
    """Output format contract for vision reverse-prompting (env keeps Stage-3; char/prop = image-only)."""
    existing_cn = str(getattr(entity, "generation_prompt_cn", "") or "").strip()
    name_lock = (
        "- 保留 name / name_en 与 CURRENT 完全一致（逐字符，禁止改名）。\n"
        "- 完整生图提示词只写入 generation_prompt_cn（自然中文短段）。\n"
        "- generation_prompt_en 必须固定为空字符串 \"\"。\n"
        "- negative_prompt_en 用简短英文；anchor_description 用 3-5 个英文短语。\n"
    )

    # Character / prop: analyze the uploaded/bound image as-is; do not force Stage-3 sheet rebuild.
    if category == "character":
        return (
            "角色分析硬约束（只按原图分析）：\n"
            f"{name_lock}"
            "- 以提供的图片为唯一视觉权威：appearance_cn / clothing / generation_prompt_cn 必须忠实描述图中可见内容。\n"
            "- 不要为了凑「四宫格/四视图」而臆造图中不存在的视角、面板或构图；图是什么构图就按什么写。\n"
            "- CURRENT 文本仅用于保留身份名与少量非冲突背景；与图片冲突时一律以图片为准。\n"
            "- generation_prompt_cn 写成可直接生图的中文描述（相貌、衣着、材质、姿态、光线、背景以图为准）。"
        )
    if category == "prop":
        return (
            "道具分析硬约束（只按原图分析）：\n"
            f"{name_lock}"
            "- 以提供的图片为唯一视觉权威：description_cn / generation_prompt_cn 必须忠实描述图中可见物体。\n"
            "- 不要为了凑「四宫格/四视图」而臆造图中不存在的视角或面板；图是什么构图就按什么写。\n"
            "- 优先写结构、材质、工艺、磨损、比例与可见细节；无手/无人物除非图中确实出现。\n"
            "- CURRENT 文本仅用于保留名称；与图片冲突时一律以图片为准。"
        )

    preserve_note = (
        "若 CURRENT 已有 generation_prompt_cn：必须保留其原有章节/标签/排版骨架与字段写法，"
        "仅按图片可见证据改写具体视觉内容；禁止改成单视角描述或其它资产类型格式。\n"
        if existing_cn
        else "CURRENT 无既有 generation_prompt_cn 时，严格按下列 Stage 3 原格式新建。\n"
    )
    common = (
        "通用硬约束（资产设计 Stage 3 原格式）：\n"
        f"{name_lock}"
        "- Clean Plate：只写画面可见物理实体；环境禁具名角色/人称。\n"
        f"{preserve_note}"
    )

    if category == "poster":
        return (
            common
            + "海报/封面 generation_prompt_cn 格式（强制）：\n"
            "- 固定 4:3 poster canvas；premium theatrical one-sheet 单张主视觉（非四宫格分镜）。\n"
            "- 写清前中后景、标题安全区与移动端 UI 净空；光学与风格服从图片证据。"
        )

    # environment
    if _entity_analysis_is_main_environment(entity):
        return (
            common
            + "主环境 generation_prompt_cn 格式（强制，四向拼图 2×2 四宫格）：\n"
            "- 首句声明：生成四向拼图基准参考图；16:9 横幅；2×2 四宫格；禁止拉成 1:1；禁止俯拍/鸟瞰。\n"
            "- 格位固定：左上=0度、右上=90度、左下=180度、右下=270度；各格眼高约 50mm；四格共享材质/光源；Clean Plate。\n"
            "- 成稿逐格写 [0度格-左上]/[90度格-右上]/[180度格-左下]/[270度格-右下]，每格按「背景→中景→前景/邻向斜切→天花地面→光照」。\n"
            "- description_cn 写俯视 360 + 0 度轴与固定实体清单；dependency_strategy.type 必须为 BaselineDefinition；visual_dependencies=[]。\n"
            "- 若图片本身已是四宫格，按四格可见内容回写；若图片是单视角，仍须输出完整四向拼图格式（其余格据空间一致性合理补齐，并在 logic 标明推断格）。\n"
            "- 严禁改成单镜头可拍空镜、§A/§B/§C 衍生三段式、或角色/道具白底四视图。"
        )
    return (
        common
        + "衍生环境 generation_prompt_cn 格式（强制，§A/§B/§C 单镜）：\n"
        "- §A：参考主环境四向拼图指定格/半空间（或上一状态空镜）。\n"
        "- §B：与参考图一致的具象清单（地面/家具/门窗/色谱/锚点；前景/中景/背景 + 上中下）。\n"
        "- §C：本镜 Delta（机位、左右重组、背景半空间）；Clean Plate；禁人物。\n"
        "- description_cn 须含本衍生独立四向自然语言；保留既有 visual_dependencies / dependency_strategy 语义。"
    )


def _build_entity_analysis_schema_instruction(entity: Any, category: str) -> str:
    format_contract = _build_entity_analysis_format_contract(entity, category)
    name_lock = str(getattr(entity, "name", "") or "Current Name")
    name_en_lock = str(getattr(entity, "name_en", "") or "")

    if category == "character":
        return f"""
{format_contract}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "characters": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "gender": "M/F",
      "role": "Role",
      "archetype": "Archetype",
      "appearance_cn": "Detailed Chinese Description (Must include height & head-to-body ratio)",
      "clothing": "Detailed Description of clothing (Must include layers, materials, colors, wear)",
      "action_characteristics": "Inferred action traits",
      "generation_prompt_cn": "只按原图可见内容写的中文生图提示词（不强迫四宫格）",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    if category == "prop":
        return f"""
{format_contract}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "props": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "type": "held/static",
      "description_cn": "Chinese Description (Mobility & Mutable States)",
      "generation_prompt_cn": "只按原图可见内容写的中文生图提示词（不强迫四宫格）",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    if category == "poster":
        return f"""
{format_contract}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "posters": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "atmosphere": "Atmosphere",
      "visual_params": "Poster/Cover/4:3",
      "description_cn": "Chinese Description",
      "generation_prompt_cn": "按上方海报 4:3 原格式写满的中文生图提示词",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Type A",
        "logic": "Cover poster"
      }}
    }}
  ]
}}
"""

    is_main_env = _entity_analysis_is_main_environment(entity)
    dep_type = "BaselineDefinition" if is_main_env else "Type A"
    dep_logic = (
        "Main environment four-direction reference grid; sole reference for derivative ENV."
        if is_main_env
        else "Derivative environment single-shot prompt with A/B/C sections."
    )
    prompt_placeholder = (
        "按上方主环境四向拼图 2×2 四宫格原格式写满的中文生图提示词"
        if is_main_env
        else "按上方衍生环境 §A/§B/§C 原格式写满的中文生图提示词"
    )
    deps_rule = (
        "visual_dependencies must be []."
        if is_main_env
        else "visual_dependencies must preserve CURRENT.visual_dependencies (do not clear ENV references)."
    )
    return f"""
{format_contract}

{deps_rule}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "environments": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "atmosphere": "Atmosphere",
      "visual_params": "{"Baseline/Interior/Day" if is_main_env else "Wide/Interior/Day"}",
      "description_cn": "Chinese Description",
      "generation_prompt_cn": "{prompt_placeholder}",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "{dep_type}",
        "logic": "{dep_logic}"
      }}
    }}
  ]
}}
"""


async def _execute_analyze_entity_image(
    entity_id: int,
    system_api_id: Optional[int] = Query(None),
    feature_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an entity (subject) image using Vision model and updates its attributes based on visual content.
    Returns the updated entity data.
    """
    logger.info(f"analyze_entity_image called for ID {entity_id}")
    
    # 1. Fetch Entity
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    project = _require_project_access(db, entity.project_id, current_user)

    if not entity.image_url:
        raise HTTPException(status_code=400, detail="Entity has no image to analyze.")

    logger.info(f"Entity found: {entity.name}, Image: {entity.image_url}")

    # 2. Resolve LLM from script_analysis function API dropdown (same list as script analysis).
    llm_config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        current_user.id,
        "script_analysis",
        system_api_id,
        context="analyze_entity_image",
    )
    api_provider = str(llm_config.get("provider") or "").strip() or None
    api_model = str(llm_config.get("model") or "").strip() or None
    api_api_key = str(llm_config.get("api_key") or "").strip() or None
    api_base_url = str(llm_config.get("base_url") or "").strip() or None
    raw_api_config = llm_config.get("config")
    api_config = dict(raw_api_config) if isinstance(raw_api_config, dict) else {}
    if not api_provider or not api_model:
        raise HTTPException(status_code=400, detail="Script analysis API dropdown has no usable Vision/LLM model. Please configure it in Function APIs.")
    
    reservation_tx = None
    reservation_tx_id: Optional[int] = None
    # Billing Check (token rules will reserve later once we have messages)
    if not billing_service.is_token_pricing(db, "analysis_character", api_provider, api_model):
        cost = billing_service.estimate_cost(db, "analysis_character", api_provider, api_model)
        billing_service.check_can_proceed(current_user, cost)

    # 3. Construct System Prompt based on Entity Type (Stage-3 original prompt formats)
    entity_type = (entity.type or "character").lower()
    analysis_category = _entity_analysis_category(entity_type)
    is_main_env = analysis_category == "environment" and _entity_analysis_is_main_environment(entity)

    llm_config = {
        "provider": api_provider,
        "api_key": api_api_key,
        "base_url": api_base_url,
        "model": api_model,
        "config": {
            **api_config,
            "__resolved_user_id": current_user.id,
            "__resolved_user_name": current_user.username,
            "__resolved_project_id": entity.project_id,
            "__resolved_action": f"资产分析({analysis_category})",
            "__selected_system_api_id": selected_dropdown_id,
        },
    }
    logger.info(f"Using Model: {api_model} (script_analysis dropdown id={selected_dropdown_id})")

    def _build_entity_analysis_error_detail(
        code: str,
        message: str,
        stage: str,
        *,
        preview: Optional[str] = None,
        repair_attempted: Optional[bool] = None,
        finish_reason: Optional[Any] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": code,
            "message": message,
            "stage": stage,
            "entity_id": entity_id,
            "provider": api_provider,
            "model": api_model,
        }
        if preview:
            payload["preview"] = str(preview or "")[:160]
        if repair_attempted is not None:
            payload["repair_attempted"] = bool(repair_attempted)
        if finish_reason not in (None, ""):
            payload["finish_reason"] = finish_reason
        return payload

    if analysis_category in {"character", "prop"}:
        base_instruction = (
            "You are an expert visual analyst. "
            "Analyze the provided subject image and UPDATE fields from what is visibly present in the image. "
            "For character/prop: image-only reverse prompting — do NOT force Stage-3 four-panel sheet reconstruction; "
            "describe the actual image composition and visible details. Keep name/name_en unchanged; generation_prompt_en=\"\".\n"
            "CRITICAL: You MUST strictly re-analyze the new image and update the anchor_description accordingly based on the new visual features. Do NOT just copy the old anchor_description."
        )
    else:
        base_instruction = (
            "You are an expert visual analyst and Stage-3 asset design specialist. "
            "Analyze the provided subject image and UPDATE the existing subject fields to match visible evidence. "
            "Rewrite generation_prompt_cn in the ORIGINAL Stage-3 asset-design prompt format for this subject type "
            "(main environment 2x2 four-direction grid; derivative ENV A/B/C; poster 4:3). "
            "Do NOT invent a new free-form prompt style.\n"
            "CRITICAL: You MUST strictly re-analyze the new image and update the anchor_description accordingly based on the new visual features. Do NOT just copy the old anchor_description."
        )
    schema_instruction = _build_entity_analysis_schema_instruction(entity, analysis_category)

    system_prompt = (
        f"{base_instruction}\n\n{schema_instruction}\n\n"
        "Constraint: Return ONLY the raw JSON object. "
        "The first non-whitespace character of your output MUST be '{' and the last character MUST be '}'. "
        "Do not include markdown formatting (like ```json), no <think> tags, no reasoning process, and no conversational text."
    )
    logger.info(
        "Entity analysis format contract | entity_id=%s type=%s category=%s main_env=%s",
        entity_id,
        entity_type,
        analysis_category,
        is_main_env,
    )

    # 4. Construct Image URL & Current Info
    
    # Prepare Current Info Context
    # Include Project Context for style consistency
    project_context = {}
    if project.global_info:
         project_context = {
             "Global_Style": project.global_info.get("Global_Style"),
             "Tone": project.global_info.get("tone")
         }

    required_prompt_format = (
        "main_environment_2x2_quad"
        if is_main_env
        else {
            "environment": "derivative_environment_abc",
            "character": "image_only_from_source",
            "prop": "image_only_from_source",
            "poster": "poster_4x3",
        }.get(analysis_category, "stage3_original")
    )
    current_info = {
        "name": entity.name,
        "name_en": entity.name_en,
        "type": entity.type,
        "analysis_category": analysis_category,
        "is_main_environment": bool(is_main_env),
        "required_prompt_format": required_prompt_format,
        "description": entity.description,
        "appearance_cn": entity.appearance_cn,
        "clothing": entity.clothing,
        "role": entity.role,
        "atmosphere": getattr(entity, "atmosphere", None),
        "visual_params": getattr(entity, "visual_params", None),
        "generation_prompt_cn": entity.generation_prompt_cn,
        "generation_prompt_en": "",
        "visual_dependencies": getattr(entity, "visual_dependencies", None) or [],
        "dependency_strategy": getattr(entity, "dependency_strategy", None) or {},
        "project_context": project_context,
    }
    
    current_info_str = json.dumps(current_info, ensure_ascii=False)

    try:
        from urllib.parse import urlparse
        import base64
        
        base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
        image_url_raw = _refresh_managed_media_url(entity.image_url, db)
        image_url_final = image_url_raw
        
        local_file_path = None
        path_part = None

        if image_url_raw:
            if image_url_raw.startswith("http"):
                parsed_url = urlparse(image_url_raw)
                if parsed_url.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
                    path_part = parsed_url.path.lstrip("/")
            else:
                # Relative path (e.g. /uploads/...)
                path_part = image_url_raw.lstrip("/")
        
        if path_part:
            possible_paths = [
                os.path.join(settings.BASE_DIR, "app", path_part),
                os.path.join(settings.BASE_DIR, path_part),
                os.path.join(os.getcwd(), "app", path_part),
                os.path.join(os.getcwd(), path_part),
                # Try finding in uploads dir explicitly if path starts with uploads
                os.path.join(settings.UPLOAD_DIR, path_part.replace("uploads/", "", 1))
            ]
            
            for p in possible_paths:
                # Resolve possible double slashes
                p = os.path.normpath(p)
                if os.path.exists(p) and os.path.isfile(p):
                    local_file_path = p
                    break
        
        if local_file_path:
            try:
                def _read_and_encode_entity():
                    with open(local_file_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    ext = os.path.splitext(local_file_path)[1].lower().replace(".", "")
                    mime = "image/png" if ext == "png" else "image/jpeg"
                    if ext == "jpg": mime = "image/jpeg"
                    if ext == "webp": mime = "image/webp"
                    return f"data:{mime};base64,{encoded_string}"
                image_url_final = await asyncio.to_thread(_read_and_encode_entity)
                logger.info(f"Converted local image {local_file_path} to Base64 (Size: {len(image_url_final)} chars)")
            except Exception as e:
                logger.error(f"Failed to encode local image {local_file_path}: {e}")
                
    except Exception as e:
        logger.warning(f"Error resolving entity image path: {e}")
        # Continue with original URL
        pass

    format_focus = {
        "character": "只按原图可见内容分析（不强迫四宫格）",
        "prop": "只按原图可见内容分析（不强迫四宫格）",
        "poster": "海报 4:3 单张主视觉",
        "environment": (
            "主环境四向拼图 2×2 四宫格（左上0/右上90/左下180/右下270）"
            if is_main_env
            else "衍生环境 §A/§B/§C 单镜格式"
        ),
    }.get(analysis_category, "Stage 3 原提示词格式")

    if analysis_category in {"character", "prop"}:
        user_analysis_text = (
            f"Here is the CURRENT information for subject '{entity.name}':\n{current_info_str}\n\n"
            "Please analyze the image.\n"
            "IMPORTANT:\n"
            f"1) {format_focus} — generation_prompt_cn / appearance / clothing / description must follow the image as authority.\n"
            "2) Do NOT invent missing four-panel views or Stage-3 sheet structure that is not in the image.\n"
            "3) CURRENT text is only for name lock and non-conflicting identity; image wins on conflicts.\n"
            "4) generation_prompt_en MUST be an empty string \"\".\n"
            "5) Keep name/name_en unchanged.\n"
            "Output contract: reply with JSON only, begin immediately with '{', and do not output any explanation or thinking text."
        )
    else:
        user_analysis_text = (
            f"Here is the CURRENT information for subject '{entity.name}':\n{current_info_str}\n\n"
            "Please analyze the image. Fuse the visual details from the image with the current information.\n"
            "IMPORTANT:\n"
            f"1) Rewrite generation_prompt_cn in the ORIGINAL Stage-3 format for this subject: {format_focus}.\n"
            "2) If CURRENT.generation_prompt_cn already exists, preserve its section/tag/layout skeleton and only refresh visual facts from the image.\n"
            "3) generation_prompt_en MUST be an empty string \"\".\n"
            "4) Keep name/name_en unchanged.\n"
            "Output contract: reply with JSON only, begin immediately with '{', and do not output any explanation or thinking text."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_analysis_text},
                {"type": "image_url", "image_url": {"url": image_url_final}},
            ],
        },
    ]
    
    try:
        logger.info("Sending request to LLM...")

        # Do NOT release DB connection here in background task, otherwise SQLAlchemy detaches models
        # _release_db_connection(db, "analyze_entity_image_llm_call")

        if billing_service.is_token_pricing(db, "analysis_character", api_provider, api_model):
            est = billing_service.estimate_reserve_tokens_from_messages(messages)
            estimated_image_tokens = 1000
            est_input = int(est.get("input_tokens", 0) or 0) + estimated_image_tokens
            est_output = int(math.ceil(float(est_input) * billing_service.RESERVE_OUTPUT_RATIO)) if est_input > 0 else 0
            reserve_details = {
                "item": "entity_image_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "estimated_image_tokens": estimated_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": int(est_input + est_output),
            }
            reservation_tx = billing_service.reserve_credits(
                db,
                current_user.id,
                "analysis_character",
                api_provider,
                api_model,
                reserve_details,
            )
            try:
                reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None

        llm_response = await llm_service.chat_completion_with_fallback(messages, llm_config)
        
        result_content = llm_response.get("content", "")
        usage = llm_response.get("usage", {})
        effective_llm_response: Dict[str, Any] = llm_response

        def _merge_usage_metrics(base_usage: Dict[str, Any], delta_usage: Dict[str, Any]) -> Dict[str, Any]:
            merged = dict(base_usage or {})
            if not isinstance(delta_usage, dict):
                return merged
            additive_keys = ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens")
            for key in additive_keys:
                if key in delta_usage:
                    try:
                        merged[key] = int(merged.get(key, 0) or 0) + int(delta_usage.get(key, 0) or 0)
                    except Exception:
                        pass
            for key, value in delta_usage.items():
                if key not in merged:
                    merged[key] = value
            return merged
        
        logger.info(f"LLM Reply Length: {len(result_content)}. Usage: {usage}")
        
        # Remove <think> blocks and robustly extract the first valid JSON payload.
        content = re.sub(r"<think>.*?</think>", "", str(result_content or ""), flags=re.DOTALL | re.IGNORECASE).strip()

        if not content:
            raise HTTPException(
                status_code=502,
                detail=_build_entity_analysis_error_detail(
                    "entity_analysis_empty_content",
                    "LLM returned empty content for entity analysis",
                    "initial_response",
                    repair_attempted=False,
                    finish_reason=(llm_response or {}).get("finish_reason"),
                ),
            )

        # Strip fenced code blocks if present.
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content, flags=re.IGNORECASE).strip()

        def _extract_first_json_payload(text: str):
            import json
            text = str(text or "")
            
            has_json5 = False
            json5_obj = _loads_json5_if_available(text)
            if isinstance(json5_obj, (dict, list)):
                return json5_obj
            if json5_obj is not None:
                has_json5 = True

            first_idx = -1
            last_idx = -1
            for i, ch in enumerate(text):
                if ch in "{[":
                    first_idx = i
                    break
            if first_idx >= 0:
                for i in range(len(text) - 1, -1, -1):
                    if text[i] in "}]":
                        last_idx = i
                        break

            if first_idx >= 0 and last_idx >= 0 and first_idx < last_idx:
                sub_text = text[first_idx:last_idx + 1]
                try:
                    if has_json5:
                        res = _loads_json5_if_available(sub_text)
                    else:
                        res = json.loads(sub_text)
                    if isinstance(res, (dict, list)):
                        return res
                except Exception:
                    pass

            decoder = json.JSONDecoder()
            for idx, ch in enumerate(text):
                if ch not in "{[":
                    continue
                try:
                    obj, _end = decoder.raw_decode(text[idx:])
                    if isinstance(obj, (dict, list)):
                        return obj
                except Exception:
                    continue
            return None

        data = _extract_first_json_payload(content)
        if data is None:
            preview = content[:300].replace("\n", " ")
            logger.warning(
                "Entity analysis JSON parse first-pass failed | entity_id=%s provider=%s model=%s finish_reason=%s content_preview=%s",
                entity_id,
                api_provider,
                api_model,
                (llm_response or {}).get("finish_reason"),
                preview,
            )

            # One-shot repair retry: ask the same model to convert output into strict JSON only.
            repair_system = (
                "You are a strict JSON formatter. "
                "Convert the user's text into a valid JSON object only. "
                "The first character must be '{' and the last character must be '}'. "
                "No markdown fences, no explanation, no extra text."
            )
            repair_user = (
                "Convert the following content to a valid JSON object that preserves the original fields as much as possible.\n\n"
                f"{content}"
            )

            try:
                repair_response = await llm_service.chat_completion_with_fallback(
                    [
                        {"role": "system", "content": repair_system},
                        {"role": "user", "content": repair_user},
                    ],
                    llm_config,
                )
                repair_text = re.sub(
                    r"<think>.*?</think>",
                    "",
                    str((repair_response or {}).get("content", "") or ""),
                    flags=re.DOTALL | re.IGNORECASE,
                ).strip()
                repair_text = re.sub(r"^```(?:json)?\s*", "", repair_text, flags=re.IGNORECASE)
                repair_text = re.sub(r"\s*```$", "", repair_text, flags=re.IGNORECASE).strip()

                repaired_data = _extract_first_json_payload(repair_text)
                if repaired_data is not None:
                    data = repaired_data
                    usage = _merge_usage_metrics(usage, (repair_response or {}).get("usage", {}) or {})
                    effective_llm_response = repair_response or effective_llm_response
                    logger.info("Entity analysis JSON parse recovered via repair retry.")
                else:
                    repair_preview = repair_text[:300].replace("\n", " ")
                    logger.error(
                        "Entity analysis JSON parse failed after repair retry | entity_id=%s provider=%s model=%s initial_finish_reason=%s repair_finish_reason=%s content_preview=%s repair_preview=%s",
                        entity_id,
                        api_provider,
                        api_model,
                        (llm_response or {}).get("finish_reason"),
                        (repair_response or {}).get("finish_reason"),
                        preview,
                        repair_preview,
                    )
                    raise HTTPException(
                        status_code=422,
                        detail=_build_entity_analysis_error_detail(
                            "entity_analysis_non_json",
                            "LLM returned non-JSON content for entity analysis",
                            "repair_parse",
                            preview=repair_preview,
                            repair_attempted=True,
                            finish_reason=(repair_response or {}).get("finish_reason") or (llm_response or {}).get("finish_reason"),
                        ),
                    )
            except HTTPException:
                raise
            except Exception as repair_err:
                logger.error(
                    "Entity analysis JSON repair retry failed | entity_id=%s provider=%s model=%s err=%s content_preview=%s",
                    entity_id,
                    api_provider,
                    api_model,
                    str(repair_err),
                    preview,
                )
                raise HTTPException(
                    status_code=422,
                    detail=_build_entity_analysis_error_detail(
                        "entity_analysis_json_repair_failed",
                        "Entity analysis JSON repair retry failed",
                        "repair_request",
                        preview=preview,
                        repair_attempted=True,
                    ),
                )

        if isinstance(data, list):
            data = data[0] if data else {}

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=422,
                detail=_build_entity_analysis_error_detail(
                    "entity_analysis_invalid_json_root",
                    "Entity analysis JSON must be an object",
                    "parsed_payload",
                    repair_attempted=data is not None,
                ),
            )
                  
        # Extract the core object based on type
        updated_info = {}
        if "characters" in data and isinstance(data["characters"], list) and len(data["characters"]) > 0:
            updated_info = data["characters"][0]
        elif "props" in data and isinstance(data["props"], list) and len(data["props"]) > 0:
            updated_info = data["props"][0]
        elif "environments" in data and isinstance(data["environments"], list) and len(data["environments"]) > 0:
            updated_info = data["environments"][0]
        elif "posters" in data and isinstance(data["posters"], list) and len(data["posters"]) > 0:
            updated_info = data["posters"][0]
        else:
            updated_info = data # Fallback if direct object

        if isinstance(updated_info, dict):
            # Stage-3 contract: full prompt lives in CN; EN field stays empty.
            updated_info["generation_prompt_en"] = ""
            # Name lock: never let reverse-prompt rename the subject.
            locked_name = str(getattr(entity, "name", "") or "").strip()
            locked_name_en = str(getattr(entity, "name_en", "") or "").strip()
            if locked_name:
                updated_info["name"] = locked_name
            if locked_name_en:
                updated_info["name_en"] = locked_name_en
            
        logger.info(f"Parsed Updated Info for Entity {entity_id}: {json.dumps(updated_info, ensure_ascii=False)[:300]}...")

        if not updated_info:
             logger.warning("updated_info is empty! LLM response might not match expected JSON schema.")

        # The original ORM instance may be detached after _release_db_connection;
        # reload a session-bound instance before applying updates.
        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Update Entity Fields
        if "base_name_en" in updated_info: entity.base_name_en = updated_info["base_name_en"]
        if "description_cn" in updated_info: entity.description = updated_info["description_cn"] # Map description_cn to description
        if "appearance_cn" in updated_info: entity.appearance_cn = updated_info["appearance_cn"]
        if "clothing" in updated_info: entity.clothing = updated_info["clothing"]
        if "action_characteristics" in updated_info: entity.action_characteristics = updated_info["action_characteristics"]
        if "role" in updated_info: entity.role = updated_info["role"]
        if "archetype" in updated_info: entity.archetype = updated_info["archetype"]
        if "gender" in updated_info: entity.gender = updated_info["gender"]
        
        if "atmosphere" in updated_info: entity.atmosphere = updated_info["atmosphere"]
        if "visual_params" in updated_info: entity.visual_params = updated_info["visual_params"]
        
        if "generation_prompt_cn" in updated_info: entity.generation_prompt_cn = updated_info["generation_prompt_cn"]
        entity.generation_prompt_en = ""
        if "negative_prompt_en" in updated_info and hasattr(entity, "negative_prompt_en"):
            entity.negative_prompt_en = updated_info["negative_prompt_en"]
        if "anchor_description" in updated_info:
            entity.anchor_description = coerce_anchor_description(updated_info["anchor_description"])
        
        if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list):
            incoming_deps = updated_info["visual_dependencies"]
            # Derivative ENV reverse-prompt must not wipe existing ENV reference chain.
            if (
                analysis_category == "environment"
                and not is_main_env
                and not incoming_deps
                and getattr(entity, "visual_dependencies", None)
            ):
                updated_info["visual_dependencies"] = entity.visual_dependencies
            else:
                entity.visual_dependencies = incoming_deps
                updated_info["visual_dependencies"] = incoming_deps
        if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
            incoming_dep = updated_info["dependency_strategy"]
            if is_main_env:
                incoming_dep = {
                    **incoming_dep,
                    "type": "BaselineDefinition",
                }
            entity.dependency_strategy = incoming_dep
        elif is_main_env:
            existing_dep = _entity_analysis_parse_jsonish(getattr(entity, "dependency_strategy", None))
            if not isinstance(existing_dep, dict):
                existing_dep = {}
            entity.dependency_strategy = {
                **existing_dep,
                "type": "BaselineDefinition",
                "logic": existing_dep.get("logic")
                or "Main environment four-direction reference grid; sole reference for derivative ENV.",
            }

        # Update Custom Attributes with Analysis Result (Save latest)
        custom_attrs = entity.custom_attributes or {}
        # Ensure dict if it came from DB as string (unlikely with SQLAlchemy JSON type but possible with SQLite text)
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
            
        custom_attrs['analysis_result'] = {
            "timestamp": now_bj_iso(),
            "content": updated_info
        }
        # Re-assign to trigger SQLAlchemy detection of mutation if needed
        entity.custom_attributes = dict(custom_attrs)


        logger.info(
            "Entity Updated. New Prompt CN Length: %s",
            len(entity.generation_prompt_cn) if entity.generation_prompt_cn else 0,
        )

        # Billing finalize (after successful parse/update)
        billing_details = _build_standard_billing_details(
            item="entity_image_analysis",
            usage_payload=usage if isinstance(usage, dict) else None,
            extra_details={
                "entity_id": entity_id,
                "request_scope": "analyze_entity_image",
            },
            routing_payload=effective_llm_response,
        )

        if reservation_tx:
            # If usage seems to miss image tokens, add a conservative estimate to avoid under-charging.
            current_input = billing_details.get("prompt_tokens", billing_details.get("input_tokens", 0))
            if current_input < 200:
                estimated_image_tokens = 1000
                billing_details["input_tokens"] = current_input + estimated_image_tokens
                billing_details["prompt_tokens"] = billing_details["input_tokens"]
                if "total_tokens" in billing_details:
                    billing_details["total_tokens"] += estimated_image_tokens
                else:
                    billing_details["total_tokens"] = billing_details["input_tokens"] + billing_details.get("output_tokens", 0)
            _finalize_model_invocation_billing(
                db=db,
                current_user=current_user,
                task_type="analysis_character",
                provider=api_provider,
                model=api_model,
                reservation_tx=reservation_tx,
                reservation_tx_id=reservation_tx_id,
                item="entity_image_analysis",
                usage_payload=usage if isinstance(usage, dict) else None,
                extra_details=billing_details,
                routing_payload=effective_llm_response,
            )
        else:
            _finalize_model_invocation_billing(
                db=db,
                current_user=current_user,
                task_type="analysis_character",
                provider=api_provider,
                model=api_model,
                reservation_tx=None,
                reservation_tx_id=reservation_tx_id,
                item="entity_image_analysis",
                usage_payload=usage if isinstance(usage, dict) else None,
                extra_details=billing_details,
                routing_payload=effective_llm_response,
            )
        
        # We no longer save the prompt as a separate asset file to avoid clutter.
        # The prompt is already saved in the entity.generation_prompt_en field.

        db.commit()
        db.refresh(entity)
        return entity

    except HTTPException as e:
        logger.error(f"Entity Analysis failed with HTTPException: {str(e.detail)}", exc_info=True)
        _cancel_reservation_quietly(db, reservation_tx_id or reservation_tx, str(e.detail))
        try:
            custom_attrs = entity.custom_attributes or {}
            if isinstance(custom_attrs, str):
                custom_attrs = json.loads(custom_attrs)
            custom_attrs['analysis_result'] = {
                "status": "error",
                "message": str(e.detail)
            }
            entity.custom_attributes = dict(custom_attrs)
            entity.image_url = None
            db.commit()
        except Exception:
            db.rollback()
        raise
    except Exception as e:
        logger.error(f"Entity Analysis failed: {str(e)}", exc_info=True)
        _cancel_reservation_quietly(db, reservation_tx_id or reservation_tx, str(e))
        try:
            custom_attrs = entity.custom_attributes or {}
            if isinstance(custom_attrs, str):
                custom_attrs = json.loads(custom_attrs)
            custom_attrs['analysis_result'] = {
                "status": "error",
                "message": str(e)
            }
            entity.custom_attributes = dict(custom_attrs)
            entity.image_url = None
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=502, detail=f"Analysis failed: {str(e)}")

@router.get("/entities/{entity_id}/latest_analysis")
def get_entity_latest_analysis(
    entity_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get the latest saved analysis result for an entity.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user)
         
    custom_attrs = entity.custom_attributes or {}
    # Handle DB Storage format (Text vs JSON)
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
        
    result = custom_attrs.get('analysis_result')
    return result or {}

@router.put("/entities/{entity_id}/latest_analysis")
def update_entity_latest_analysis(
    entity_id: int,
    data: AnalysisContent,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest analysis result without applying it.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user)
         
    custom_attrs = entity.custom_attributes or {}
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
    
    # Update analysis result with timestamp
    result = custom_attrs.get('analysis_result', {})
    if not isinstance(result, dict): result = {}
    
    result['content'] = data.content
    result['timestamp'] = now_bj_iso() # Update timestamp on edit
    
    custom_attrs['analysis_result'] = result
    entity.custom_attributes = custom_attrs  # Reassign for SQLAlchemy detection if Dict
    
    db.commit()
    return custom_attrs['analysis_result']

@router.post("/entities/{entity_id}/apply_analysis")
def apply_entity_analysis(
    entity_id: int,
    data: Optional[AnalysisContent] = None, # Optional payload to override stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) analysis result to update Entity fields.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    _require_project_access(db, entity.project_id, current_user)
    
    updated_info = {}
    
    # 1. Determine Source
    if data and data.content:
        updated_info = data.content
        # Optionally save this new content as latest too? YES.
        custom_attrs = entity.custom_attributes or {}
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
        
        custom_attrs['analysis_result'] = {
            "timestamp": now_bj_iso(),
            "content": updated_info
        }
        entity.custom_attributes = custom_attrs
    else:
        # Load from stored
        custom_attrs = entity.custom_attributes or {}
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
        
        result = custom_attrs.get('analysis_result', {})
        if isinstance(result, dict):
            updated_info = result.get('content', {})
    
    if not updated_info:
        raise HTTPException(status_code=400, detail="No analysis content provided or found to apply.")

    # 2. Apply Updates (Same logic as analyze_entity_image)
    if "name_en" in updated_info: entity.name_en = updated_info["name_en"]
    if "base_name_en" in updated_info: entity.base_name_en = updated_info["base_name_en"]
    if "description_cn" in updated_info: entity.description = updated_info["description_cn"] 
    if "appearance_cn" in updated_info: entity.appearance_cn = updated_info["appearance_cn"]
    if "clothing" in updated_info: entity.clothing = updated_info["clothing"]
    if "action_characteristics" in updated_info: entity.action_characteristics = updated_info["action_characteristics"]
    if "role" in updated_info: entity.role = updated_info["role"]
    if "archetype" in updated_info: entity.archetype = updated_info["archetype"]
    if "gender" in updated_info: entity.gender = updated_info["gender"]
    
    if "atmosphere" in updated_info: entity.atmosphere = updated_info["atmosphere"]
    if "visual_params" in updated_info: entity.visual_params = updated_info["visual_params"]
    
    if "generation_prompt_cn" in updated_info: entity.generation_prompt_cn = updated_info["generation_prompt_cn"]
    if "generation_prompt_en" in updated_info: entity.generation_prompt_en = updated_info["generation_prompt_en"]
    if "anchor_description" in updated_info:
        entity.anchor_description = coerce_anchor_description(updated_info["anchor_description"])
    
    if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list): 
            entity.visual_dependencies = updated_info["visual_dependencies"]
    if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
            entity.dependency_strategy = updated_info["dependency_strategy"]

    db.commit()
    db.refresh(entity)
    return entity

