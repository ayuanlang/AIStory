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
    if dep_type in ("BaselineDefinition", "StyleReference"):
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
            "【0度方向】",
            "【四面内容基准】",
            "四宫度数=",
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
    if has_env_dep and dep_type != "StyleReference":
        return False
    # No ENV dependency and no derivative markers → treat as main/baseline.
    return dep_type in ("", "Original", "BaselineDefinition", "StyleReference")


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
            "- 以提供的图片为唯一视觉权威：generation_prompt_cn 必须忠实描述图中可见物体；description_cn 必须为空字符串 \"\"。\n"
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
            + "主环境回写只保留四段：【定位】、【主体外形】、【色彩说明】、【四向拼图】。\n"
            + "- 【定位】按序保留。CURRENT 已有的时段、风格和场所身份保留，只按图片可见证据改。不写画面左、画面右。\n"
            + "- 【主体外形】每个主体只一句：外形、大小、材质、纹样、颜色。大小保留具体米或该向无限制，按图片可见证据改这一句，不另起一套米。不要在四壁或四格里再写外形和材质。【色彩说明】整节保留，按图片可见证据改这一节，不拆进四格。成稿不写【六面一次】【北壁】【东壁】【南壁】【西壁】【光学说明】【构图】这些标题。\n"
            + "- 【四向拼图】开头一句共享：光比、色温、柔硬、焦段、景深、半影、色板，四格不重复。画布只一行：16:9，2×2 四宫格；四宫度数=左上0度｜右上90度｜左下180度｜右下270度。四格标题是[0度格-左上·北]、[90度格-右上·东]、[180度格-左下·南]、[270度格-右下·西]。每格写角标=、正面：、左侧面：、右侧面：、中部：、构图：、源体可见=、源体画布位=、高度带=、来光、影子投向、辅光、纵深光层、镜后整包不入画。原点是一具主体的中心：优先舞台中部、中心确实在中部的地上主体，地面可以；中部没有则用边上的地上主体。左侧面和右侧面各量该侧主体在镜头前方的近面到原点的距离，不取墙心，不用场径代替。中心在纵深对齐且没有伸进远离镜头的，不写入侧面。较近的一侧是基准，另一侧超过这侧距离的 2 倍才只写不可见。侧面禁止写开敞、通向外景。机位朝本格正面，到正面的距离取近面垂距。正对的墙只有一个远离镜头的米数。顺着长边的正面照写该端远景或封闭面。落在左或右、超过较近一端 2 倍的长条端只写不可见，禁止远天际只见短头。沿短边正面是短墙且不超过另一侧 2 倍时写这面短墙，超过则只写不可见。长条形空间和长条形主体同一套，不单开长路。每格五面都要有：正面、左侧面、右侧面、中部、上。左右侧按测算可写不可见，行必须在。镜后只写不入画，不写那一面的主体。同一参照物只有一份北米、东米，四格只旋转这一份，旋回后必须相同。构图只写方法（对称、中心、纵深、框中、对角线）和倾向，不点名主体，不写前景、中景、远景、纵深色层。每格先写画布坐标：原点是该主体的中心，在地面上、画面左右正中、地平线以下；横轴从画面左到画面右，纵轴从靠近镜头到远离镜头，上轴从地面向上。这一具写中心就在画布原点。大小只在【主体外形】写一次，四格不写大小，不写高、宽、厚、长。入画的每一件只写两轴：画面左或画面右或左右对齐，以及远离镜头或靠近镜头或纵深对齐，两轴都带米。两轴来自开篇北米和东米。只写一条轴或只写缝档等于没有定位。不写主舞台、北0东0、东南西北。光学段写光源、源形、源体画布位、光线从、射向、影子投向、辅光，位置和光线方向已经转成画面左、画面右、靠近镜头、远离镜头。缝档不代替这两轴。离平地和窗台离地是高度。方位字只留在格标题和角标。四格不写外形、材质、纹样、颜色、光比、色温、焦段。\n"
            + "- 四宫不写可见=、左邻壁=、右邻壁=、站在=、落点=、画面落位=、机位=、远锚=、底面=、心点=、距原点=、Key世界向=。不把四壁正文抄进格子。不在成图上画东南西北示意图。\n"
            + "- 不输出角度衍生或状态衍生。description_cn 必须为 \"\"。generation_prompt_cn 必须非空。默认 dependency_strategy.type=BaselineDefinition 且 visual_dependencies=[]。风格依赖主环境才用 StyleReference，且只挂另一块主环境。\n"
            + "- 图片已是四宫格：四壁主景回写开篇对应壁，四格画面回写正面、左侧面、右侧面、中部。图片是单视角：保留 CURRENT 开篇和未入画的格，logic 标明推断向。\n"
            + "- 严禁另起【四面内容基准】。严禁把成稿收成单张 16:9 空镜来顶替 2×2。严禁改成角色或道具四视图。\n"
        )
    return (
        common
        + "衍生环境 generation_prompt_cn 格式（强制，截取放大；第一刀只切割，不写几何/楼底）：\n"
        "- §A（仅 logic）：所属主环境= + 四宫度数=左上0度｜右上90度｜左下180度｜右下270度 + 截取宫格（左上0度/右上90度/左下180度/右下270度，与 N 同核）；禁写开篇拓扑/楼底。主环境资产已存在时，用正则匹配其 `四宫度数=` 后按该行度数裁切对应宫格。\n"
        "- anchor_description（强制）：不另选。照抄程序已从现场编排写入的 `简要特征=`。那是本场选用该衍生时点名的环境参考主体，每条只写名称和所在位置：正面、左侧面、右侧面、机位后不可见。须全部保留。没有这串时才写该角正面最多 3 个简要主体名，并标（正面）。禁止整体环境锚点、禁止挂靠锚点、禁止背景=/画左=/画右=/画外=。\n"
        "- §B 第一刀：所属主环境={名}。angle_key={名}|{N}。四宫度数=左上0度｜右上90度｜左下180度｜右下270度。截取宫格={左上0度|右上90度|左下180度|右下270度}。机位=望向={正北|正东|正南|正西}｜远锚={该向后景最远可见主体}｜禁以画外主体定位。禁止重写桌椅朝向、左右对调、扇区换边。请严格要求按对应主环境「{名}」四向拼图参考图，截取并放大其中对应的明确宫格位置（{宫格}），不要重新描述画面细节，直接作为本镜头的最终画面。切割衍生环境时均按16:9固定比例，并保证高分辨率。只切割，不要改画。成稿须为单张完整镜头：禁止保留四向拼图的宫格分割线、宫格边框、格标/角标、十字拼缝或任何拼图装配痕迹。\n"
        "- §B 衍生的衍生：所属主环境={名}。angle_key={名}|{N}。以已切割的同角衍生「{同角已切割衍生名}」参考图为本镜头最终画面。16:9，高分辨率。不要改构图，不要重切宫格，不要描述未改实体。禁止画回宫格分割线、格标或拼缝。禁止复述陈设/开篇拓扑/坡向。\n"
        "- 依赖图（最高；对应必须准确）：第一刀视角衍生 visual_dependencies 必须且仅能 [\"ENV:[所属主环境名]\"]。衍生的衍生必须且仅能 [\"ENV:[同角已切割衍生名]\"]（如 ENV:[0度港口办公室]），N 必须与本行相同；禁止挂他角切割图；禁止在已有同角切割时回挂主环境四向拼图；禁止 CHAR/PROP/海报/他主。对应参考图未就绪不得当无参考文生。\n"
        "- §C（衍生的衍生）：只写相对同角切割图真正变化的项。禁止描述未改实体（未改实体名及其描述一句都不出现）。变化实体名必须与原清单/主环境已写名逐字符相同，不得重新取名、润色、缩写或同义替换。可写光色/氛围短增量，或该已锁名实体的形状短差值。禁止另起一间房；不改依赖图；Clean Plate；禁人物。\n"
        "- description_cn 必须为 \"\"；generation_prompt_cn 必须非空且可检索 所属主环境={主环境名}；衍生元数据/Delta 写入 dependency_strategy.logic。"
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
      "description_cn": "",
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
      "description_cn": "",
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
      "description_cn": "",
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
        "按上方两段写满：开篇保留世界锁；【四向拼图】只写正面、左侧面、右侧面、中部和画面光句。禁止可见=、左邻壁=、站在=。"
        if is_main_env
        else "按上方衍生环境 §B 截取放大句式写（点名所属主环境四向拼图对应宫格；禁重写细节）"
    )
    anchor_placeholder = (
        "3-5 English anchor phrases"
        if is_main_env
        else "简要特征=主体名（正面|左侧面|右侧面|机位后不可见）"
    )
    deps_rule = (
        "visual_dependencies must be [] and type=BaselineDefinition, unless this is a floor-split style-dependent main environment: then type=StyleReference and visual_dependencies=[\"ENV:[风格父主环境名]\"] (another main ENV only; still write a full independent four-direction prompt)."
        if is_main_env
        else "visual_dependencies: first-cut angle derivatives must be [\"ENV:[所属主环境名]\"] (four-panel). Derivatives-of-derivatives must be [\"ENV:[同角已切割衍生名]\"] with the same N as this row. Do not hang a different angle, and do not hang the main four-panel when the same-angle crop already exists."
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
      "description_cn": "",
      "generation_prompt_cn": "{prompt_placeholder}",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "{anchor_placeholder}",
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
         try:
             from app.core.style_mode_catalog import resolve_style_mode
             resolved_style = resolve_style_mode(
                 project.global_info.get("style_mode"),
                 project.global_info.get("base_positioning"),
             )
         except Exception:
             resolved_style = project.global_info.get("style_mode") or project.global_info.get("base_positioning")
         project_context = {
             "style_mode": resolved_style,
             "base_positioning": project.global_info.get("base_positioning") or resolved_style,
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
            "主环境两段：开篇六面一次（下/上/中/北壁/东壁/南壁/西壁+主光/辅光+主舞台区/挂靠锚点）+ 四格只写正面/左侧面/右侧面/中部/源体画布位/影子投向；禁止左邻壁=、站在=、可见="
            if is_main_env
            else "衍生环境 §B 统一主环境切机位（机位=望向=｜远锚=可见后景最远；禁重写桌椅）"
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

        # Snapshot before release — ORM instances detach after close().
        locked_name = str(getattr(entity, "name", "") or "").strip()
        locked_name_en = str(getattr(entity, "name_en", "") or "").strip()
        current_user_id = int(getattr(current_user, "id", 0) or 0)
        had_reservation = bool(reservation_tx_id)
        _release_db_connection(db, "analyze_entity_image_llm_call")
        reservation_tx = None  # use reservation_tx_id only after release

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
            if locked_name:
                updated_info["name"] = locked_name
            if locked_name_en:
                updated_info["name_en"] = locked_name_en
            
        logger.info(f"Parsed Updated Info for Entity {entity_id}: {json.dumps(updated_info, ensure_ascii=False)[:300]}...")

        if not updated_info:
             logger.warning("updated_info is empty! LLM response might not match expected JSON schema.")

        # Reload session-bound instances after _release_db_connection.
        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        if current_user_id > 0:
            reloaded_user = db.query(User).filter(User.id == current_user_id).first()
            if reloaded_user is not None:
                current_user = reloaded_user

        # Update Entity Fields
        if "base_name_en" in updated_info: entity.base_name_en = updated_info["base_name_en"]
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
        # description_cn is no longer LLM content; UI/import use generation_prompt_cn as description substitute.
        prompt_cn_for_desc = str(updated_info.get("generation_prompt_cn") or entity.generation_prompt_cn or "").strip()
        desc_cn = str(updated_info.get("description_cn") or "").strip()
        if prompt_cn_for_desc:
            entity.description = prompt_cn_for_desc
        elif "description_cn" in updated_info:
            entity.description = desc_cn
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
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(entity, "custom_attributes")


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

        if had_reservation:
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
        _cancel_reservation_quietly(db, reservation_tx_id, str(e.detail))
        try:
            entity = db.query(Entity).filter(Entity.id == entity_id).first()
            if entity is None:
                raise
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
        _cancel_reservation_quietly(db, reservation_tx_id, str(e))
        try:
            entity = db.query(Entity).filter(Entity.id == entity_id).first()
            if entity is None:
                raise
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
    prompt_cn_for_desc = str(updated_info.get("generation_prompt_cn") or entity.generation_prompt_cn or "").strip()
    desc_cn = str(updated_info.get("description_cn") or "").strip()
    if prompt_cn_for_desc:
        entity.description = prompt_cn_for_desc
    elif "description_cn" in updated_info:
        entity.description = desc_cn
    if "anchor_description" in updated_info:
        entity.anchor_description = coerce_anchor_description(updated_info["anchor_description"])
    
    if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list): 
            entity.visual_dependencies = updated_info["visual_dependencies"]
    if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
            entity.dependency_strategy = updated_info["dependency_strategy"]

    db.commit()
    db.refresh(entity)
    return entity


class EnvironmentConsistencyBody(BaseModel):
    prompt: Optional[str] = None


@router.post("/entities/{entity_id}/environment-consistency")
async def check_environment_consistency(
    entity_id: int,
    payload: Optional[EnvironmentConsistencyBody] = None,
    system_api_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare each grid and its image with the main-environment opening.

    Subject count, facing, and position must match the opening. When they
    disagree, rewrite the grid cells or the derived prompt. The opening stays
    unless the checker marks an internal contradiction in the opening itself.
    """
    from app.services.promo_planner import resolve_image_url_for_llm
    from app.services.script_analysis_flow.environment_consistency import (
        ConsistencyApplyError,
        apply_consistency_writes,
        build_consistency_messages,
        classify_checked_prompt,
        entity_consistency_payload,
        find_owning_main_environment,
        is_environment_entity,
        parse_consistency_payload,
        plan_consistency_writes,
        resolve_checked_prompt,
    )

    entity = db.query(Entity).filter(Entity.id == entity_id, _active_entity_clause()).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    _require_project_access(db, entity.project_id, current_user)
    if not is_environment_entity(entity):
        raise HTTPException(status_code=400, detail="一致性检查只用于主环境和衍生环境。")
    if not str(getattr(entity, "image_url", "") or "").strip():
        raise HTTPException(status_code=400, detail="还没有生成图片，无法做一致性检查。")

    checked_prompt = resolve_checked_prompt(entity, getattr(payload, "prompt", None))
    if not checked_prompt:
        raise HTTPException(status_code=400, detail="没有可对照的生成提示词。")
    kind = classify_checked_prompt(entity, checked_prompt)
    main_entity = find_owning_main_environment(db, entity) if kind != "main" else entity
    if kind != "main" and main_entity is None:
        raise HTTPException(status_code=400, detail="找不到所属主环境，无法核对世界物理。")

    llm_config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        current_user.id,
        "script_analysis",
        system_api_id,
        context="environment_consistency",
    )
    api_provider = str(llm_config.get("provider") or "").strip() or None
    api_model = str(llm_config.get("model") or "").strip() or None
    api_api_key = str(llm_config.get("api_key") or "").strip() or None
    api_base_url = str(llm_config.get("base_url") or "").strip() or None
    raw_api_config = llm_config.get("config")
    api_config = dict(raw_api_config) if isinstance(raw_api_config, dict) else {}
    if not api_provider or not api_model:
        raise HTTPException(status_code=400, detail="剧本分析的模型下拉没有可用的视觉模型。")

    reservation_tx = None
    reservation_tx_id: Optional[int] = None
    if not billing_service.is_token_pricing(db, "analysis_character", api_provider, api_model):
        cost = billing_service.estimate_cost(db, "analysis_character", api_provider, api_model)
        billing_service.check_can_proceed(current_user, cost)

    image_url_final = await resolve_image_url_for_llm(str(entity.image_url or ""), db)
    if not image_url_final:
        raise HTTPException(status_code=400, detail="生成图片无法读取，暂时不能做一致性检查。")

    messages = build_consistency_messages(
        image_url=image_url_final,
        entity=entity,
        main_entity=main_entity,
        checked_prompt=checked_prompt,
        kind=kind,
    )
    call_config = {
        "provider": api_provider,
        "api_key": api_api_key,
        "base_url": api_base_url,
        "model": api_model,
        "config": {
            **api_config,
            "__resolved_user_id": current_user.id,
            "__resolved_user_name": current_user.username,
            "__resolved_project_id": entity.project_id,
            "__resolved_action": "环境一致性检查",
            "__selected_system_api_id": selected_dropdown_id,
        },
    }
    main_entity_id = int(getattr(main_entity, "id", 0) or 0)
    current_user_id = int(getattr(current_user, "id", 0) or 0)

    if billing_service.is_token_pricing(db, "analysis_character", api_provider, api_model):
        est = billing_service.estimate_reserve_tokens_from_messages(messages)
        estimated_image_tokens = 1000
        est_input = int(est.get("input_tokens", 0) or 0) + estimated_image_tokens
        est_output = int(math.ceil(float(est_input) * billing_service.RESERVE_OUTPUT_RATIO)) if est_input > 0 else 0
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "analysis_character",
            api_provider,
            api_model,
            {
                "item": "environment_consistency_check",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "estimated_image_tokens": estimated_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": int(est_input + est_output),
            },
        )
        try:
            reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
        except Exception:
            reservation_tx_id = None

    had_reservation = bool(reservation_tx_id)
    _release_db_connection(db, "environment_consistency_llm_call")
    reservation_tx = None

    try:
        llm_response = await llm_service.chat_completion_with_fallback(messages, call_config)
        result_content = str((llm_response or {}).get("content", "") or "")
        usage = (llm_response or {}).get("usage", {}) if isinstance(llm_response, dict) else {}
        try:
            parsed = parse_consistency_payload(result_content)
        except ConsistencyApplyError:
            repair = await llm_service.chat_completion_with_fallback(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是严格的 JSON 整理器。把用户文本转成一个 JSON 对象。"
                            "第一个字符必须是 {，最后一个字符必须是 }。"
                            "保留 consistent、summary、revised_prompt、revised_main_prompt。"
                            "不要 Markdown，不要解释。"
                        ),
                    },
                    {"role": "user", "content": result_content[:120000]},
                ],
                call_config,
            )
            repair_usage = (repair or {}).get("usage", {}) if isinstance(repair, dict) else {}
            if isinstance(usage, dict) and isinstance(repair_usage, dict):
                for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
                    if key in repair_usage:
                        try:
                            usage[key] = int(usage.get(key, 0) or 0) + int(repair_usage.get(key, 0) or 0)
                        except Exception:
                            pass
            parsed = parse_consistency_payload(str((repair or {}).get("content", "") or ""))

        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        main_entity = db.query(Entity).filter(Entity.id == main_entity_id).first() if main_entity_id else None
        if current_user_id > 0:
            reloaded_user = db.query(User).filter(User.id == current_user_id).first()
            if reloaded_user is not None:
                current_user = reloaded_user

        plan = plan_consistency_writes(entity, main_entity, checked_prompt, parsed)
        entities_by_id = {int(entity.id): entity}
        if main_entity is not None:
            entities_by_id[int(main_entity.id)] = main_entity
        touched = apply_consistency_writes(entities_by_id, plan["writes"])
        if touched:
            db.commit()
            for row in entities_by_id.values():
                if int(row.id) in touched:
                    db.refresh(row)

        billing_details = _build_standard_billing_details(
            item="environment_consistency_check",
            usage_payload=usage if isinstance(usage, dict) else None,
            extra_details={
                "entity_id": entity_id,
                "request_scope": "environment_consistency",
                "checked_kind": kind,
            },
            routing_payload=llm_response if isinstance(llm_response, dict) else None,
        )
        if had_reservation:
            current_input = billing_details.get("prompt_tokens", billing_details.get("input_tokens", 0))
            if current_input < 200:
                billing_details["input_tokens"] = int(current_input or 0) + 1000
                billing_details["prompt_tokens"] = billing_details["input_tokens"]
                if "total_tokens" in billing_details:
                    billing_details["total_tokens"] = int(billing_details.get("total_tokens") or 0) + 1000
        _finalize_model_invocation_billing(
            db=db,
            current_user=current_user,
            task_type="analysis_character",
            provider=api_provider,
            model=api_model,
            reservation_tx=None,
            reservation_tx_id=reservation_tx_id,
            item="environment_consistency_check",
            usage_payload=usage if isinstance(usage, dict) else None,
            extra_details=billing_details,
            routing_payload=llm_response if isinstance(llm_response, dict) else None,
        )
        return {
            "consistent": bool(plan["consistent"]),
            "summary": plan["summary"],
            "checked_kind": plan["kind"],
            "updated_targets": plan["updated_targets"],
            "updated": [entity_consistency_payload(entities_by_id[item_id]) for item_id in touched],
        }
    except ConsistencyApplyError as exc:
        _cancel_reservation_quietly(db, reservation_tx_id, str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException as exc:
        _cancel_reservation_quietly(db, reservation_tx_id, str(exc.detail))
        raise
    except Exception as exc:
        logger.error("Environment consistency check failed: %s", exc, exc_info=True)
        _cancel_reservation_quietly(db, reservation_tx_id, str(exc))
        raise HTTPException(status_code=502, detail="一致性检查失败，提示词没有改动。") from exc

