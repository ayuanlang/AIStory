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
            + "主环境 generation_prompt_cn 格式（强制，折中两段式：物理世界一次 → 四宫只留画面一套；成稿=分点自然语言+标签，现有锁键不得省略）：\n"
            "- 体例：必须分点（每条 `- `），用标签区分：【定位】【六面一次】【北壁】【东壁】【南壁】【西壁】【光学说明】【色彩说明】【构图】【四向拼图】。每条用自然语言写清，但开篇场径=/围合=/心点=/封闭面=/主光=/竖边=/通达=/U=/下口=/上口=/在桌=/椅面朝向= 与四宫正面：/左侧面：/右侧面：/中部：/挂靠锚点=/锚点落=/四宫度数= 必须原样写在对应条内，禁止写落点=/站在=/画面长边=/画面四端=，禁止只写散文丢掉格式化锁。四宫禁止写可见五面=/后景=/中景=/中部=可见/*照抄=。禁止收成一段无标签总述。\n"
            "- ①开篇六面一次（全文一处，不得少）：风格定位（文学原文只作输入，禁止照抄）。须可检索 `六面一次` + `原点=中心` + `罗盘=正北=0｜正东=90｜正南=180｜正西=270` + `场径=` + `面积测算=` + `下=` + `上=` + `中=` + `北壁=` + `东壁=` + `南壁=` + `西壁=`。物理世界先于机位：主体+围合+场径+面积测算+光源与光照方向（须可检索 `主光=` + `辅光=` + `Key世界向=` + 源 `心点=`）写在开篇。`面积测算=南北{北+南}米×东西{东+西}米｜档=开间|窄道`。场径由体量锁死，禁止为凑五面虚扩。距对面/焦距由已锁世界按空间档+长宽分算。负空间只记账：距对面大于室内满距（远锚场径+镜头后场径）写是，否则写否。有墙或障碍时距对面取该方向离原点的无障碍最大距离，或可见三面里最小一面的距离；禁止默认满距−0.5米，禁止再加1～2米到墙外。仍正对对面主体，后壁不入镜，禁止画出墙后第二间房，禁止偏航。小屋/舱/窄向禁止越墙。斜角来自偏航不是焦距算错。开间/通高20–28mm；广场/野外/校场18–24mm；仙境外景/美景/云海16–22mm（比厅堂更广，禁鱼眼、<16）。90/270邻向是可见五面之一，必须入镜，禁止升成第二正立面，禁止点名主体。室外广角只扩天+地+远景，敞向禁止补近壁。半退或短轴仍35mm不得假装已扫两邻。原点锁开篇全部具名主体（含每一茶杯/盏/盘，须心点=或台面心点=），不锁机位：须写原点=中心｜坐标轴=正北轴+正南轴+正东轴+正西轴。开篇须可检索物理系闭集=；每一具名可定位主体须心点或台面心点+距原点或相对宿主+占地+占场；远山/远路/天际/人流剪影不是可定位主体，禁止给它们心点当锚。开篇须抄规划 整体环境锚点=/主舞台区=/舞台范围=/舞台大小=/舞台净空=/挂靠锚点=/锚点落=，并写舞台占地=（步档译米，禁改档）。规划缺挂靠则补锚：取距原点最大的可定位件，无则取最近落地件，写补锚依据=。广袤无近处唯一件时只认规划已造的特异可定位挂靠，禁止把整片沙/草/天/远山当锚。每一可定位件须触点=无或触点=宿主:接触部位；占地除已锁触点共享边外禁止重叠。画布坐标系原点=主舞台区心（四格同一个剧情点，只旋转；挂靠不是画布原点，除非挂靠心与主舞台区心相距≤0.3米）；轴=画面左↔右＋远离镜头↔靠近镜头（下方）。四宫可见可定位件相对原点最少写偏挂靠左右距＋离镜头远近距两点，可加高差与开篇触点；远近只认本格u，禁止抄他格；邻向挂靠可作原点但禁止画面正中是该挂靠。四宫机位按挂靠锚点，不用原点定位摄影机。每格写可见=/正面=/中部=/左邻壁=/右邻壁=/镜后=/挂靠锚点=/锚点落=/画面原点=中点/画面落位=/落点=/机位=/远锚=正面。开篇只写世界原点+心点+竖边。四宫只留画面一套：正面/左邻壁/右邻壁必须写底面=（封闭面或远景）；有贴附写贴附层=（在底面之前一档，左右按开篇心点旋到本格），有檐写压顶=；禁止墙+案或墙+檐扁平加号。中部=远离<5、镜后=对向整包不入镜。四格服从R1–R17：锚点落=中则站在=挂靠锚点正{反方向}（禁止主舞台区正）；偏位挂靠先旋后移；通铺封闭面中心可左右居中，偏轴贴附件/开口件禁止中心左右居中（禁止与封闭面捆一条居中），残差左右不是换槽，同壁墙与贴附必须同一面同一槽；可见可定位件必须相对本格参考锚写画面位置与占地大小（挂靠入画用挂靠，否则本格最远或最近可定位件，排除远山远路）；禁止把占场百分数抄进四宫；禁止格内抄逐件相对锚定位总则；邻封不夺正面禁止铺满画心；封向贴附写在这面墙前一档+本格左右档+同一槽，禁止写成墙+案扁平加号；敞口必须先写远处没有实墙，开口件悬在空档里，禁止贴在墙上或贴在远景上，禁止用邻封或对向封补远处整面；座具件数锁在画布一次钉座具件数四格守恒；各格画面落位只写本格两条怎么摆，禁止写四格都是/禁止只画一条禁止再加一条，禁止凳A凳B；90/270竖边东西则左右各一条顺纵深禁止横在桌前；成稿禁止靠左N成/远离镜头N成，必须写中心在+按开篇占地铺开；Key落在侧向敞口或侧向亮窗禁止为亮部偏航，禁止邻向整面或对向封闭面灌进本格正面；锚点落=邻向则挂靠只进靠左/靠右短头且远离成=正面分量（贴望向0则远离0，禁止默认3/5，禁止写入正面）；同一壁件两侧望格左右成对调且远离成相同；每格必须写正面围合=+左邻围合=+右邻围合=；正面/左邻壁/右邻壁必须写底面=，有贴附写贴附层=或压顶=；正面必须带本格望向字（0°北向或正北、90°东向或正东、180°南向或正南、270°西向或正西）且主核词截自开篇该向封闭面或远景原词；靠左/靠右/镜后同样必须带该槽所对向字；禁止四格正面同一向字或同一封闭面主核词。禁止写后景=/中景=/中部=可见/左邻=/右邻=/本格朝向=/*照抄=。近镜头向与不入镜向同属镜后不可见。位置推导：世界x=东−西、y=北−南；本格ψ=0/90/180/270；u=y·cosψ+x·sinψ（+远离，−镜后）；v=x·cosψ−y·sinψ（+靠右，−靠左）。代入0°u=y v=x；90°u=x v=−y；180°u=−y v=−x；270°u=−x v=y。锚点落=中且挂靠不在原点：先旋后移 u'=u−u挂 v'=v−v挂，落点只用撇后值；挂靠左右0，正面禁止再左右0。u<0或贴镜后壁写镜后=不入镜，禁止落点写近镜头成；u≥0写落点=靠左|靠右|远离镜头，成数=该轴米÷该向场径×5。反推x=u·sinψ+v·cosψ、y=u·cosψ−v·sinψ须回开篇心点。台面先合成宿主+台面再旋。长短边两端同式：差只在u则画面长边=远离镜头（近端镜后不入画），差只在v则靠左↔靠右。禁止写竖边=/心点=/近镜头成。邻壁远离成必须=该件正面分量，贴北东0则远离0，禁止默认远离3。同壁≥2件必须各写落点，禁止2张捆成靠左0靠右0，禁止一根键靠左与靠右同时>0。90°北壁靠左成=270°北壁靠右成且两格远离成相同；南壁对向同理。四宫只留画面一套：正面=/中部=/左邻壁=/右邻壁=/镜后= + 落点= + 正面围合=。禁止写后景=/中景=/左邻=/右邻=。正面具名≤3；封写封闭面，敞写远景+开口件（R3）；禁止2张/8具/及配套写入正面，桌凳不进正面。中部桌逐张≤4，条凳不点名，柱须拆开禁止靠左+靠右同时写。靠左靠右写该邻向整包（封闭面+该向贴附，合计≤3），禁止把该向贴附拆到正面或对侧。正面每格只写一次。四格站位与正面落点服从R1–R9。机位句禁止对着正东|正西|正南|正北，禁止远锚=正北|正东|正南|正西；槽内必须写本格望向字。有竖边的可见件必须写画面长边=。四宫禁止点条凳名。中或本格正面挂靠落点=中点或远离镜头5；邻向挂靠按推导写靠左或靠右＋远离成=该件正面分量（贴北东0则远离0），禁止远离5，禁止默认远离3。可见件必须写成相对画面原点的偏画面米+离镜头米，禁止写落点=。中部挂靠不得当远锚。规划已写东南西北须逐字继承，禁止改挂。南北跨≠东西跨时，长轴格与短轴格的距对面与焦距必须分算，禁止四格抄同一组数；短轴格焦更广，墙外则负空间=是。90/270常沿短轴，禁止抄0/180的距与焦，禁止为邻向门柜偏航。四宫必须写可见=/正面=/中部=/左邻壁=/右邻壁=/镜后=。四宫写可见五面=/正面=/中部=可见/*照抄= =失败。天花+地面+正面+中部+左邻壁+右邻壁必须入镜，不以机位/焦距限制可视性。靠左/靠右写该邻向整包短名，禁止把该向贴附拆到正面或对侧，禁止邻壁全文。正面只写本格望向封闭面或远景，禁止邻向整面或单件居中当唯一正面（R3+R4+R8）。禁止「贴边长件侧视只露短头」。禁止写可见面=/可见=部分/原则上大角度见五面。四宫禁止回写世界向；必须写本格源体可见+源体画布位+高度带+影子投向。每面该槽先写围合面再写主体：围合=封须槽头可检索封闭面=（连续立面材质/纹理，板壁|粉壁|砖墙|石壁|舱壁），禁止只用门柜桌顶替墙；围合=敞须槽头可检索远景=（天际/街/沙/海/山/云），禁止留空、禁止补实墙。缺封闭面或远景导致换角另造背景=失败。每面该槽全部主体+心点+材质+开闭只写一遍。规划只给自然语言主体、所属向、`围合=`（封|敞）与 `向距上限=`（窄|开|无限制，无米数）；场径/心点/距原点由本环节裁定，必须逐字继承围合与向距上限，禁止改档或超上限。规划未给米数=正常，禁止回流。规划误写米数按尺度闭集重锁，logic 标规划米数已重锁。敞或无限制向写场径={向}无限制，禁止虚造近壁。四宫禁止写可见面=/可见=部分/原则上大角度见五面。机位落在该向上限内。光影须可检索 `主光=` + `辅光=` + `Key世界向=`（可选 `点缀=`）。Key须与时段同核：晨东/午南/夕西/夜=室内灯；禁止把背日开口写成斜阳主光。天井Fill不得夺主。换角不换太阳、不关灯；禁止每格朝远锚自起一盏太阳。禁止再抄一遍可见动机光/实用光同名灯。禁止 `本向光变`。禁止同一主体写第二遍。靠边桌只在中=或所属壁写 `心点=`/`距原点=`/`占地=`/`占场≈`/`落边=`。贴墙件距原点≈该向场径且同壁互差≤0.5米；同壁≥2件须 `共面=是`（+是同平面贴附，不是第二面墙）。落边桌距原点+占地半边不得穿墙，禁止把桌距抄成场径，桌禁写椅面朝向=。非正方件（含栏/梯/路）须竖边=南北走向|东西走向并写两端锚；东缘西缘竖边=南北走向，南缘北缘竖边=东西走向；楼梯另写U=与下口=上口=；场内路另写通达=；挂桌座具须在桌=北侧|东侧|南侧|西侧；有前后向椅须椅面朝向=正北|正东|正南|正西（功能面）。成稿禁止写F=。四宫禁止站在=原点、禁止距原点=定位机位。室内家具心点仍用原点。禁止站在=柱/桌/柜全名。中或本格正面须写站在=挂靠锚点正南|正西|正北|正东；邻向/镜头后须写站在=主舞台区正，禁止对着挂靠正中望过去。禁止距{柱/桌}=。同款多件（立柱列）不得做机位参照。中=件只在开篇用心点锁世界位。指定五面与中部必须可见，不以机位/焦距限制可视性。不虚扩场。机位不落入桌柜占地。舱轴场写舱轴前后左右。\n"
            "- 数量预检先行：固定实体须有明确总数；同质多件须有总数、分组/分边、逐具朝向与顺序，且总数=分项和；门/窗/楼梯总数显式；每扇窗棂须有横×纵格阵与同墙顺序。禁止“若干/数把/多张/一些/成排/散座”等模糊数量词；缺项时 logic 标 upstream_missing_env_inventory_quantification 并保留原 Index 锁，禁止猜数，但 generation_prompt_cn 必须非空（骨架+已锁具名实体）。\n"
            "- 通高两层仅当须共享外形（大堂+回廊可互望）：开篇拓扑须分列下层与上层具名实体；禁止“二楼同楼下/上层继承一层”；跨层同类件须标所属楼层。二层内部（客房/账房等不共享外形）是独立主环境，禁止画进一层当上层；可 StyleReference 挂一层主环境作风格参考，仍须独立写满本块四向。\n"
            "- 两层不复述：①开篇=`六面一次`（下/上/中/四壁+光源）。禁止照抄文学。禁止另起【四面内容基准】。禁止 `本向光变`。禁止 `桌位闭集`。【四向拼图】只留画面一套：正面：/左侧面：/右侧面：/中部：/镜后/挂靠锚点=/锚点落=/本格原点对准=，禁止写落点=/可见=/左邻壁=/右邻壁=，禁止原点/对面机位，禁止写后景=/中景=/中部=可见/心点=/*照抄=，禁止回写开篇 Key世界向或心点；必须写本格已旋画布光句（源体可见+源体画布位+高度带+影子投向）。窗亮口/灯焰/火塘开篇须出光口=且心点在出光口占地内，禁止光闸写宿主=；源体可见跟出光口所在壁，禁止用Key世界向斜向对向把侧壁窗判成镜头后；非出光口窗禁止写成主光口；体积光有无四格同核。在桌先判长边或短边，长边禁止写成尽头；座具只认在桌与竖边的平行或垂直，禁止假定主位=短端；每个可见主体每格从开篇重写左右米与远近米，开篇在西的望东必须更靠近、望西必须更远离，在东的对调，在北的望北必须更远离、望南必须更靠近，符号反了=失败；南北场径与东西场径不等时，平行望向的场径是纵深、垂直望向的场径是左右，垂直望向的格把较长轴画成纵深=失败；原点色点=RGB(255,0,255)且1像素，落在主舞台区心地面，其他材质禁止这个RGB，禁止十字圆光晕文字；每件位置、朝向、走向相对该点，缺原点色点=失败；开篇须写主体分组，四面各一组、中区按套分组，一组一个核心；各格先写核心的朝向走向位置，成员写相对核心的位置距离走向朝向，走向跟核心这一格的长向，四格抄同一句在左边沿纵深=失败；同一句用与连接两个码、或用总句、沿墙序、座具把数代替第二个码=失败；编号表里本格看得见的码缺自己的左右米和远近米、或核心入画却省略成员=失败；门、窗、抽屉、柜门、箱盖在看见的格只写侧立面、不写开还是合、或不写朝哪边开、或两格开合词不同=失败；敞侧有柱栏坊阶时远景短头写在第一句、或0°左侧一列在180°仍留在左侧、或把另一壁的台阶画到这一侧=失败；台上每只碗须单独写排布=左右排布或纵深排布且米数比桌心，纵深排布两只都写更远离、或四格都写左右排布、或桌子入画却漏一只=失败；每把凳的长向必须写成左右排布或纵深排布，写成画面左右或远离镜头、或缺自己的两端米、或两端都在画面同一侧却把一端写成对侧=失败；核心镜后仍把该组凳或杯画进画面正中=失败；原点=主舞台区心，长方形沿长边分左段中段右段，顺着长边的正反两格纵深相加等于全长，两格都写全长=原点回到几何中点=失败；挂靠不在主舞台区心上时禁止把望向该挂靠的格对准挂靠；开篇北东南西四面必须写全；四宫入画只认视场公式 u>0 且 |v|≤u×k 且 |h-1.6|≤u×k×9/16，k 按焦距查 k16=1.12、k18=1.00、k20=0.90、k24=0.75、k28=0.64、k35=0.51、k50=0.36；端距>正面场径×k 的那一侧写画面端出画，出画不是删墙；公式内写成出画=失败；公式外的端被画进本格=失败；拆墙、越墙、俯仰或改焦距把公式外的端拍进来=失败；凳椅写成两端同深沿画面左右或长端纵向=失败；望东把东侧凳写成更靠近、望西把东侧凳写成更远离=失败；一张桌子的凳数等于开篇该桌凳数，禁止再在画面左和画面右各加一条；凳子缺两端米、写成两端同深沿画面左右或长身顺纵深或顺纵深放置、或非对准凳写成偏画面对齐0=失败；椅面与所在侧同向（左凳朝左、右凳朝右、近凳朝近、远凳朝远）=失败；90度或270度竖边垂直望向的凳未写长向=画面左右、或未写横在靠近镜头或远离镜头的那条边上、或仍写成贴在画面左和画面右=失败；正方桌未写左右跨等于近远跨=失败；竖边垂直望向的栏、柱列、城垣必须左右跨=开篇长、近远跨=开篇厚，两端共用一个离镜头米，同条每一件各写一个偏画面米，禁止把两端南北米写成两个离镜头，禁止格内写北端南端东端西端，近远跨大于左右跨=把横条画成纵深；转角两侧必须同一组偏画面米和离镜头米，米数不同=断开；垂直望向的栏或柱列从转角沿纵深伸进远景=失败；端甲或端乙接到邻壁却缺转角是同一个点、侧墙只写沿纵深延伸、或把厚度远侧写成云海远山深渊远景、或写成高耸入云、沿南北线、沿东西线、只露侧立面而不写远离端=失败；竖边垂直望向的阶或栏写成跟着侧墙=失败；横条必须写明端甲端乙谁在画面左谁在画面右；高低两端都在画面同一侧时禁止把一端写到对面；栏长于本格开间时左右两端出画，近远仍是栏厚，禁止改成贴在画面一侧通向远景的纵深走廊；该侧其余件必须各写两端米，只写侧影=该侧蒸发；有竖边的件本格重写走向，平行望向写靠近一端与远离一端各一米，垂直望向写左端与右端各一米且两端同深，0度180度与90度270度必须对调，四格同一句走向=失败；有椅面朝向或墙面朝向的件本格重写朝向画面哪一侧，四格同一句朝向=失败；正方圆不写长短轴，但每格写四条边落在靠近、远离、画面左、画面右，左右跨等于近远跨等于边长，贴凳的边在0度180度与90度270度必须换轴，四格都把凳写在画面左右或把正方画成长桌=失败；幡旗匾有心点的每格写偏画面与离镜头，望向正对所在壁时进正面且禁止留在画面一侧，望向与该壁垂直时只进侧面，格内写东侧或西侧=失败；离平地不旋转；竖边∥望向时长边椅心点在画面左或右且长边仍沿纵深，竖边⊥望向时心点在近侧或远侧且长边沿画面左右；椅面朝与在桌侧拆开核，位置与朝向默认都相对桌子（椅面默认朝桌心，与所在侧对向），开篇明文另锁才改旋，禁止用朝镜头或朝大门当默认；开篇同一在桌侧的多把必须同侧沿长边铺开禁止拆到对边；开篇主体编号表每一件按心点旋进本格对应槽，镜后整包不入画，禁止漏件、禁止改槽、禁止表外补件、禁止同一件两套落点，两点必须心点减Oc；挂靠不在本格正面禁止对准挂靠正中，四格里只有望向等于锚点落的那一格对准挂靠，其余对准主舞台区，挂靠只进侧面两点，禁止再写挂靠在画面左或右；长凳先写两端米：顺着望向靠近一端与远离一端各一个离镜头米，禁止只写一个同深心点；垂直望向左端与右端各一个偏画面米；一个码一句，甲与乙的侧沿不算乙已入画；同写对准主舞台区的格，90度离镜头米必须等于0度偏画面米，90度偏画面米必须等于0度离镜头米取反，对不上=换了原点；同一件必须两类剪影各两格：竖边与望向平行的两格贴一侧沿纵深，垂直的两格横排且两端同深；四格都沿纵深或都左右并排=失败；台面上东西分开南北相同的两只，0度180度横行，90度270度一近一远，四格都横行=失败；禁止先写完一格再抄进另一格只改左右；垂直望向的长条必须写成横在远处、左端与右端离镜头同深，禁止画成通向镜头的纵深条；顺着望向必须贴在画面一侧沿纵深并写两端，禁止只写一根侧影，禁止把正对格的门面抄进侧面；画布须写开篇主体四宫落位与座具件数四格守恒=开篇加阿拉伯数字把；凡有竖边的桌/案/凳/椅/床/榻须写四边落幅：端甲/端乙落在画面哪一侧，两条长边落在靠近/远离或画面左/右，左右跨=与近远跨=只换轴不改数，0/180与90/270必须对调；禁止写短头朝向镜头、长端纵向、长端横向、长身伸进纵深；分居两条长边的台面件各跟自己的长边，禁止收成一条对齐0；只有本格原点对准点名的那一件写对齐0同深0；每一入画像先写可见面（哪一侧、同一深度或沿纵深、从左到右或从近到远），再写偏画面米和离镜头=更远离|更靠近|同深；禁止离镜头后直接跟米，禁止把距原点原样写入离镜头；同一轴垂直望向禁止写成近处或远端，顺着望向禁止写成两端同深；路/廊/城垣仍写沿长侧或沿短侧，不套四边落幅的禁词；走廊/楼道/窄道的窄向格进深=路宽或该向场径，正面墙近处全锐，禁止抄沿长侧近中远三层或虚扩短轴，光学同档锐度不等于四格同一世界进深，命中窄向时窄向格须写进深=路宽或该向场径且正面墙就在近处，禁止把窄向浅进深口号写进画布；锚点落=中禁止对准主舞台区；对准件必须偏画面对齐0且离镜头同深0，禁止把开篇北南米写入对准件偏画面；270度邻壁开口必须与90度左右对调，禁止一格左右都有门洞，禁止无口邻壁补亮洞；270度是90度的左右对调加近远对调，禁止抄0度左右分坐或180度近椅当主位，禁止只留靠近镜头一张椅；有座具每格须写本格可见座具=N把并逐把点名，禁止用两把侧椅顶替N；档①正面须写左端到右端连续铺满，邻壁禁止占远处半幅；邻向格中部禁止首句写空地面；90度270度禁止把开篇北南米写入离镜头（半旋），对准件必须离镜头=同深0；短名[@]内出现东南西北=失败。\n"
            "- ③【四向拼图】：画布首句必须写 `四宫承开篇=以上【定位】与【六面一次】的同一物理世界，只换角度翻译观察，四格同一房间；画面视觉必须与世界物理同核`。四格不是四套房间，只是对开篇同一物理世界的不同角度翻译观察；禁止另造与开篇冲突的墙/桌/光。该句只写画布一次，禁止抄进各格画面落位。16:9，2×2；必须可检索锁定行 `四宫度数=左上0度｜右上90度｜左下180度｜右下270度`；四格书写序 `0左上→90右上→180左下→270右下`；画布只钉一次 `四宫承开篇` + `只换角度翻译观察` + `画面视觉必须与世界物理同核` + `左右罗盘=同一房间四向连拍，每格须见天花+地面+三立面加中部，立面只三=正面+左邻壁+右邻壁，禁第四立面，禁蒸发，禁三面并排，禁第二正立面` + `远锚独占` + `四格闭集` + `转角正交` + `one wall one plane` + `五面加中部` + `四格同物同貌` + `同样主体四格生成必须保持一致` + `座具件数四格守恒` + `逐件相对锚定位` + `宫格角标` + `远处只画本格望向` + `镜后只写整包不入画` + `延续体换角改画面长边` + `旗列跟宿主同可见` + `不拉主体` + `90度与270度正面互斥` + `0度与180度正面互斥` + `四面风格同核` + `画布坐标系` + `立面只三` + `同距同列` + `壁束守恒` + `核销按件不按面` + `沿墙轴` + `法线轴` + `槽壁一一` + `同壁沿墙序守恒` + `窗灯源体可见跟出光口所在壁` + `非出光口不夺主` + `体积光四格同核` + `开篇主体四宫落位` + `本格可见座具=N把` + `正面皮左右端` + `邻壁不占远半` + `对向开口左右对调` + `中部家具与具名件四格必须保持一致；正面墙面与远景必须按本格望向切换且正对主体=开篇该向` + `five faces plus center must be visible; named furniture identical across panels; facing wall must switch by compass and match opening 六面一次; all panels share one style system`。各格正面围合抄开篇该向，禁止把某一格写成永远敞口或永远封口；270度正面围合抄开篇西向，禁止写死远处没有实墙。四格同一套可见句式，禁止为某两格另写专段。成稿禁止出现「贴边长件侧视只露短头」。每格必须写角标=（0度·望北｜90度·望东｜180度·望南｜270度·望西）+可见=（天花+地面+正面+中部+左邻壁+右邻壁）+正面=+中部=+左邻壁=+右邻壁=+镜后=+正面围合=+挂靠锚点=+锚点落=+画面原点=中点+画面落位=+落点=+机位=+远锚=正面+同物同貌=是。成图每格左上必须画度数+望向+东南西北示意图（N上E右S下W左，本格望向加粗三角）。90度与270度远处只画的核词必须互斥；270度远处只画开篇西向封闭面或远景，镜后=东向整包不入画；0度与180度同理。画面落位只写正向：远处只画本格望向、左边侧墙只沿纵深、右边侧墙只沿纵深、镜头后方整包不入画。画面落位写禁止把或点名对向核词=失败。镜后=只写{向}向整包不入画。禁止写后景=/中景=/左邻=/右邻=/中部=可见/本格朝向=/*照抄=。内部路由不入成稿：望北则左邻壁=西右邻壁=东；望东则左邻壁=北右邻壁=南；望南则左邻壁=东右邻壁=西；望西则左邻壁=南右邻壁=北。每格必须写画面原点=中点/落点=/画面落位=/机位=/远锚=正面。画面落位必须按五句写：远处只画开篇该望向封闭面或远景，铺满最远处；左边侧墙只沿纵深铺开；右边侧墙只沿纵深铺开；画面正中是挂靠，按占地占一块面积；其余可定位可见件须写相对本格参考锚的左右/远近与占地大小（比该锚更小|接近|更大）；座具按相对桌子写本格两条怎么摆（横摆或顺纵深），禁止在格内写四格都是；左邻壁/右邻壁是该邻向整壁，是左边或右边那一面邻壁，不是正面墙的左边或右边，相对参考锚在其画面左或右，按开篇占地占一块面积，可沿纵深铺开，远处整面只画本格望向；封向贴附必须写在这面墙前一档、比墙更靠近镜头、中心带本格左右档、相对参考锚、和这面墙同一槽，禁止写成墙+案；敞口必须先写远处没有实墙，开口件悬在这面空档里，禁止贴在墙上或贴在远景上，禁止把邻封或对向封补进远处整面；正面/左邻壁/右邻壁必须写底面=，有贴附写贴附层=或压顶=；座具只写本格摆法；件数守恒只写在画布座具件数四格守恒；禁止格内写一共N条四格都是；桌子和凳子分开写在画布，禁止凳A凳B；90/270且竖边东西则左右各一条顺纵深，禁止横在桌前；镜头后方整包不入画。残差偏右禁止把正面贴附改写右邻壁=。同壁件分槽=失败。禁止靠左N成。禁止只开中心位目录。禁止四格同一画面剪影。四宫机位句禁止写对着正东|正西|正南|正北、禁止远锚=正北|正东|正南|正西；正面槽必须写本格望向字（90°须东向或正东，270°须西向或正西）。开篇六面禁止落点=/靠左成。各面按开篇心点译成本格落点：正面围合=开篇该望向围合档，正面=该向封闭面或敞向远景+开口短名，靠左/右邻壁=邻壁短头（≤2名）。禁止写心点=/正面照抄=/右邻照抄=/天花照抄=。邻向整面写入本格正面=失败。违反R1–R11=失败。同壁件分槽=失败。敞口缺远处没有实墙或缺悬在、或写贴在这面墙上/贴在这面远景上=失败。画面落位缺同一面=失败。画面落位写四格都是或禁止只画一条，禁止再加一条=失败。画布缺座具件数四格守恒或缺逐件相对锚定位或缺宫格角标或缺远处只画本格望向或缺镜后只写整包不入画或缺延续体换角改画面长边或缺旗列跟宿主同可见或缺不拉主体或缺90度与270度正面互斥=失败。270度画面落位在开篇西向=封时写远处没有实墙=失败。开篇延续体（栏/梯/路）缺竖边或缺两端锚=失败。楼梯缺U=或下口上口=失败。场内路缺通达=失败。南北走向在90度270度缺画面长边沿画面左右、或在0度180度缺沿远离镜头=失败（东西走向对调）。四格同一延续体画面长边同向=失败。开篇缺物理系闭集=失败。各格画面落位再抄逐件相对锚定位=或物理系闭集=或宫格角标=失败。每格缺角标=失败。任一格正面或远处整面出现对向望向封闭面或远景或贴附核词=失败。对向两格远处整面主核词相同=失败。画面落位写相对远山或相对远路=失败。挂靠入画的格画面落位缺相对=失败。缺左邻围合=/右邻围合=或正面缺本格望向字或正面写成邻向墙主核词=失败。偏轴贴附件或开口件写左右0=失败（不要求远离=5）。封闭面+案炉捆一条左右0=失败。禁止另起未锁件，禁止蒸发。正面围合=敞时正面必须是该向远景+开口件，禁止虚造近壁，禁止把邻向封闭面铺满正面，禁止把开口件贴到邻向封闭面上，禁止开口件左右0。四宫禁止后景=/中景=；开篇六面禁用镜头前中后景锁家具。禁止原点/对面机位（对面=/距对面=/负空间=/镜头朝=/灭点=/焦距=/站在=原点）。成稿禁止写可见面=/可见=部分/原则上大角度见五面。四格站位只认R1：中或本格正面=站在挂靠锚点正{反方向}对着挂靠正中；邻向/镜后壁挂=站在主舞台区正{反方向}，禁止对着挂靠正中。禁止为偏位门窗或单柱偏航成墙角两点透视。锚点落=中的偏位挂靠必须平移到挂靠正反向（R2），禁止留在中轴正对远锚壁。壁挂邻向/对向格禁止围柜转。锚点落=中须写中部=挂靠名、正面=远锚。锚点落=邻向或镜后却站在=挂靠锚点正=失败（混用R1两轴）。四宫机位句禁止写过挂靠心点/机位心点=/光轴。禁止照抄块。落边桌禁压正南/正北/正东/正西轴（正交分量须≥占地半边+0.6米）。开篇禁止写斜向引导视线当构图。开间/通高20–28mm；广场/野外18–24mm；仙境外景/美景16–22mm。负空间只对账距对面是否大于室内满距，禁止用扫邻/五面倒推。六面是开篇世界；镜头后那一面不入镜。天花+地面+正面+中部+左邻壁+右邻壁必须入镜，不以机位/焦距限制可视性。窄/敞不得补墙。半退或短轴仍35mm不得假装已扫两邻。90/270禁止为邻向门柜偏航。禁止为凑左右邻改鱼眼或一格画四向全员。不因广角本身失败。斜角来自偏航不是广角。敞向禁止因广角补近壁。禁止把四格闭集/站在再解释成长句。四宫机位行禁止写望向=、禁止写画左=/画右=、禁止写壁/墙。禁止写望北：左=。每格只写一行：「可见=天花+地面+正面+中部+左邻壁+右邻壁｜正面=｜中部=｜左邻壁=｜右邻壁=｜镜后=｜正面围合=｜挂靠锚点=｜锚点落=｜站在=｜远锚=正面｜同物同貌=是」。前景=可省。禁止画左=/画右=/后景=/中景=/中部=可见/*照抄=。远锚=正面。机位句禁止距原点=/世界位=/光轴=过原点。禁止站在=原点。禁止距{柱/桌}=。同款多件（立柱列）不得做机位参照。四宫禁止写机位心点=。四站各一（中或本格正面=挂靠锚点正南/西/北/东；邻向/镜头后=主舞台区正南/西/北/东）。禁止之南/之西。禁止写{方位}角·{壁}侧沿。禁止远锚写非挂靠门柜窗名。中部挂靠不得当远锚。禁止逐字照抄开篇壁文。禁止俯拍。\n"
            "- 远锚独占：每格只正对开篇已锁的那一世界方位。四格光轴都合远锚方位，一律正对，禁45°墙角。四宫可见件写中心位自然语言，禁止成数坐标；近镜头向或不入镜向写整件在镜头后方不入画。邻壁短头禁止写成落在远离镜头的正面。远锚=正面。邻向是可见五面之一，必须入镜；禁止蒸发，禁止展成第二正立面，禁止点名非挂靠主体。开敞向禁止被实墙补上。贴墙件距原点必须≈该向场径（互差≤0.5米）。落边只许北缘|东缘|南缘|西缘|中，禁止用角当落边。桌总数=具名方桌/圆桌数，壁面案台不算桌。中=净空不得与中区件形制连写。四格一律画面槽：正面：｜左侧面：｜右侧面：｜中部：｜镜后｜挂靠锚点=｜锚点落=｜本格原点对准=。禁止写可见=/左邻壁=/右邻壁=/落点=。四宫禁止距原点=/后景=/中景=/中部=可见/*照抄=。落边桌禁压坐标轴。四角立柱不是原点，90/270近柱须左右对称。禁止只写东侧地面；禁止机位心点=；禁止站在=原点或距{柱/桌}=；禁止两格同站。南北跨≠东西跨必须分算距与焦，禁止四格抄同一组。物理世界（含光）先于机位：距对面/焦距由已锁世界按轴反算；负空间只对账距对面是否大于室内满距；四宫必须写正面：/左侧面：/右侧面：/中部：/挂靠锚点=/锚点落=/本格原点对准=，禁止写落点=/可见=/左邻壁=/右邻壁=；禁止「贴边长件侧视只露短头」；禁止虚扩场径凑左右邻。四宫禁止回写世界向；必须写本格源体可见+源体画布位+高度带+影子投向。主件心点须北南+东西两个分量，四格世界心点不得漂。落边件按心点×望向投影。禁止{方位}角·侧沿。禁止四宫复述开篇六面。上=天井/环廊禁止当远锚。\n"
            "- 各向机位正对输入该向内容；四方正交；禁止偏斜/墙角构图/荷兰角。\n"
            "- 中区地面家具只在开篇锁一次；四宫只译落点，禁止中部照抄/正面照抄，禁止改朝向。四格同物同貌：中部家具与具名件四格必须保持一致；正面墙面与远景必须按本格望向切换并与开篇该向同核。非正方件（长方凳/条凳/长桌/床/沙发/案/栏/栏杆/石栏/旗列/柱列/索/楼梯/台阶/石阶/阶梯/路/道/街/巷/甬道）开篇须写竖边=南北走向|东西走向；延续体另写两端锚；东缘西缘竖边=南北走向，南缘北缘竖边=东西走向；楼梯另写U=与下口=上口=；场内路另写通达=从端甲通向端乙。挂桌座具/条凳须写在桌=北侧|东侧|南侧|西侧；有前后向的椅/沙发须写椅面朝向=正北|正东|正南|正西（大门|桌心|挡风等）。成稿禁止写 F=。桌禁写椅面朝向=。四宫可见延续体须写画面长边：南北走向0度180度沿远离镜头、90度270度沿画面左右，东西走向对调；四格同一延续体画面长边同向=失败。开篇有旗帜设计或旗列须写跟宿主=且与宿主同竖边同两端；旗座列占地长边跟宿主栏同数量级，禁止一座2×2基座冒充整列。宿主栏入画的格每一面具名旗必须写该面色相、图样、形状原词，并写色相依次是；缺色序、只写阵旗、整列一个色相、或同一码四格色相词不同=失败；只在正对格写旗、邻格只写栏=失败。望向与主光世界向相差180度时源体画布位必须是镜头后、对齐，写成偏画面左或偏画面右、或该格天空画出金盘、或影子写成画面左或画面右=失败。不拉主体：开篇一文一物，同一具名禁止两个槽，槽后散文禁止点名邻壁或对向具名；四宫件只进所属向对应槽，邻壁只沿纵深，禁止铺到画面正中或占远处整面，镜后整包不入画；占场≈禁止抄进四宫。邻轴件远近：远近只认本格u，禁止抄他格远离/靠近句。邻壁件u≈0，只沿该侧纵深，禁止当远锚或画面正中；挂靠若在邻壁短头入画可作画布原点，远近只认本格u。望向壁件u≈该向场径，在远处。锚点落=本格邻向时画面落位须写层次=，按本格u近到远。竖边与望向正交的延续体禁止画成通向正面的进深走廊。邻向开口禁止画到本格正面墙。每封壁须壁束=皮|口|贴，封闭面=必须等于皮，禁止口或贴写入封闭面=；同面只锁平面，核销按件：该壁入画时皮与每一口、每一贴各有点名+两点，画了皮或口不顶替贴；不同沿墙位写沿墙序且每件两点，同沿墙位写法线前后；沿墙序只排谁更左/更远，禁止把「画面右是」写成偏画面右；偏画面必须心点减Oc，禁止沿墙位=北半直接写偏左；侧视远近只认旋后沿墙轴，禁止用距挂靠当离镜头；序与米不等式反向=失败；每一口/贴开篇须锁沿墙长=+法线厚=+四向最远=，开口另锁窗台离地=且四格同一个米；正对须写左端与右端，侧视须写靠近端与远离端，禁止只露侧立面收束，禁止只钉心点，偏轴口禁止为对称改成画面左右居中；对向两格同一世界半位禁止都画面左；A壁口/贴禁止进入B壁槽；侧视禁止只用同面句；转角开口不换壁、不省略。四面风格同核：开篇风格定位+场所风格+建筑术语系+渲染制式四格同档，各向立面可按开篇材质不同，禁止另起第二套语法。正对主体=开篇该向封闭面或远景；邻槽禁止写正立面。画布须钉画布坐标系=与立面只三=与同距同列=。每格立面正好三张：正面+左邻壁+右邻壁，天花地面不算立面，禁止第四立面、同壁折墙、三张都当正立面并排。开篇两件相对原点同一世界轴垂直距离互差不超过0.5米须锁同排=东西或同列=南北；南北分量同则同排东西，东西分量同则同列南北；四宫须沿一条画面轴齐平，禁止斜列或一前一后。开篇在桌=某侧的中区端头件（锅盏烛架等，不限座具）与同一世界向壁贴附是两件，换角只改相对桌子哪一端，禁止画到该向壁的案台灶上；南北走向桌在桌=北侧→0度桌子远离镜头那一端｜90度桌子画面左端｜180度桌子靠近镜头那一端｜270度桌子画面右端。开篇长边两侧都有椅则90度270度必须近侧一条加远侧一条都入画，禁止只留靠近镜头一条横凳。本格望向围合=封且该向无门窗开口，禁止写成从这面墙射入或墙上开光洞，该向墙只写受光面与投影。四宫禁止写椅面背向镜头或椅面面向镜头。远景里的远山远路不锁心点。\n"
            "- 门/窗/楼梯唯一落位：完整门扇或贴墙整跑梯只写在所属壁；四宫禁止点名邻壁，禁止另造正面。\n"
            "- 楼梯须在开篇声明上行朝向 U；禁止四宫都画成迎面拾级。\n"
            "- 歧义控制：一名一物；一物一位；坐标≠朝向。\n"
            "- description_cn 必须为 \"\"；generation_prompt_cn 必须非空。默认 dependency_strategy.type=BaselineDefinition 且 visual_dependencies=[]。若 CURRENT/Index 为楼层切分后的风格依赖主环境：type=StyleReference，visual_dependencies=[\"ENV:[风格父主环境名]\"]（仅另一块主环境，禁挂角度衍生）；generation_prompt_cn 仍须独立写满四向，只对齐材质/年代/色系/工艺，禁抄父环境家具与拓扑。\n"
            "- 若图片本身已是四宫格，四壁主景回写开篇 `北壁=`/`东壁=`/`南壁=`/`西壁=`，可见五面+中部回写【四向拼图】；若图片是单视角，仍须输出开篇+四宫两段式（其余壁据空间一致性合理补齐，logic 标明推断向）。\n"
            "- 构图与纵深只在开篇写一次。四宫写可见五面+中部+挂靠机位，禁止原点/对面机位。\n"
            "- 严禁另起【四面内容基准】；严禁指望模型自行旋转邻面；严禁把构图/纵深收成一篇单镜头 16:9 空镜来顶替 2×2；严禁改成角色/道具浅灰底四视图。"
        )
    return (
        common
        + "衍生环境 generation_prompt_cn 格式（强制，截取放大；第一刀只切割，不写几何/楼底）：\n"
        "- §A（仅 logic）：所属主环境= + 四宫度数=左上0度｜右上90度｜左下180度｜右下270度 + 截取宫格（左上0度/右上90度/左下180度/右下270度，与 N 同核）；禁写开篇拓扑/楼底。主环境资产已存在时，用正则匹配其 `四宫度数=` 后按该行度数裁切对应宫格。\n"
        "- anchor_description（强制）：抄规划 `整体环境锚点=`。`锚点落=北|东|南|西` 仅该向度数衍生可见挂靠，`锚点落=中` 则四向皆可见。可见行=`整体环境锚点={名}｜挂靠锚点={名}`；不可见行只写 `整体环境锚点={名}`，禁止带挂靠。禁止再写背景=/画左=/画右=/画外=。\n"
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
        "按上方主环境两段式写满：开篇六面一次（下/上/中/四壁+光源，禁抄文学）→【四向拼图】只切机位；禁止复述主体"
        if is_main_env
        else "按上方衍生环境 §B 截取放大句式写（点名所属主环境四向拼图对应宫格；禁重写细节）"
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
            "主环境两段式：开篇六面一次（下/上/中/北壁/东壁/南壁/西壁+主光/辅光+主舞台区/挂靠锚点）+ 四宫写可见五面+中部+挂靠机位；禁止抄文学、禁止四宫复述非挂靠主体"
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

