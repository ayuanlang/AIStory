# -*- coding: utf-8 -*-
"""Shot-submit debug + promo/script-mode prompt helpers."""
from __future__ import annotations

import logging
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from app.services.llm_service import llm_service

logger = logging.getLogger("api_logger")

def _is_shot_submit_debug_enabled() -> bool:
    return str(os.getenv("SHOT_SUBMIT_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_ref_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        return [raw] if raw else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return []


def _extract_ref_display_name(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
        path = urllib.parse.unquote(parsed.path or "")
        base_name = os.path.basename(path.rstrip("/"))
        if base_name:
            return base_name
        if parsed.netloc:
            return parsed.netloc
    except Exception:
        pass
    return raw


def _build_ref_display_names(value: Any, limit: int = 20) -> List[str]:
    refs = _normalize_ref_list(value)
    names: List[str] = []
    seen: set = set()
    for ref in refs:
        name = _extract_ref_display_name(ref)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


_PROMO_TYPE_HINTS = (
    "宣传",
    "推广",
    "营销",
    "品牌",
    "campaign",
    "promotion",
    "promotional",
    "advert",
    "advertising",
    "brand",
    "corporate",
    "product",
    "tourism",
    "cta",
    "conversion",
)


def _looks_like_promo_type(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in _PROMO_TYPE_HINTS)


def _has_promo_generator_input(global_info: Any) -> bool:
    gi = dict(global_info or {})
    planner_input = gi.get("promo_planner_input")
    if isinstance(planner_input, dict):
        enterprise = planner_input.get("enterprise_info") if isinstance(planner_input.get("enterprise_info"), dict) else {}
        campaign = planner_input.get("campaign_demand") if isinstance(planner_input.get("campaign_demand"), dict) else {}
        for value in (
            enterprise.get("brand_name"),
            enterprise.get("brand_intro"),
            enterprise.get("product_info"),
            campaign.get("user_raw_text"),
            campaign.get("cta"),
        ):
            if str(value or "").strip():
                return True
        assets = enterprise.get("image_assets")
        if isinstance(assets, list) and assets:
            return True
    if isinstance(gi.get("promo_planner_result"), dict) and gi.get("promo_planner_result"):
        return True

    promo_input = gi.get("promo_generator_input")
    if not isinstance(promo_input, dict):
        return False

    for key in (
        "promo_type",
        "campaign_objective",
        "target_audience",
        "key_message",
        "core_highlights",
        "conversion_cta",
    ):
        if str(promo_input.get(key) or "").strip():
            return True
    return False


def _should_use_promo_prompts(global_info: Any, req_type: Any = None, req_extra_notes: Any = None) -> bool:
    gi = dict(global_info or {})

    if _looks_like_promo_type(req_type):
        return True

    if _looks_like_promo_type(req_extra_notes):
        return True

    if _has_promo_generator_input(gi):
        return True

    saved_story_input = gi.get("story_generator_global_input")
    if isinstance(saved_story_input, dict):
        if _looks_like_promo_type(saved_story_input.get("type")):
            return True
        if _looks_like_promo_type(saved_story_input.get("extra_notes")):
            return True

    if _looks_like_promo_type(gi.get("type")):
        return True

    return False


def _normalize_generator_kind(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if raw in {"promo", "promotion", "promotional"}:
        return "promo"
    if raw in {"story", "narrative", "film"}:
        return "story"
    return None


def _pick_first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_script_mode_key(script_mode: Any) -> str:
    raw = str(script_mode or "").strip().lower()
    if "ip模式" in raw or "series ip" in raw or "ip mode" in raw:
        return "series_ip"
    if "trailer" in raw or "预告" in raw:
        return "trailer"
    if "short drama" in raw or "短剧" in raw:
        return "short_drama"
    if "feature film" in raw or "电影" in raw:
        return "feature_film"
    if "action feature" in raw or "动作片" in raw:
        return "action_feature"
    if "情绪驱动" in raw or "emotion-driven" in raw or "emotion driven" in raw:
        return "emotion_driven"
    if "romance" in raw or "emotional" in raw or "爱情情感" in raw:
        return "romance_emotional"
    if "mystery" in raw or "thriller" in raw or "悬疑惊悚" in raw:
        return "mystery_thriller"
    if "comedy" in raw or "light" in raw or "喜剧轻快" in raw:
        return "comedy_light"
    if "xianxia" in raw or "fantasy" in raw or "仙侠奇幻" in raw:
        return "xianxia_fantasy"
    if "sci-fi" in raw or "sci fi" in raw or "科幻冒险" in raw:
        return "sci_fi_adventure"
    if "period" in raw or "wuxia" in raw or "古装武侠" in raw:
        return "period_wuxia"
    if "workplace" in raw or "现代职场" in raw:
        return "modern_workplace"
    if "horror" in raw or "恐怖" in raw:
        return "horror"
    if "cyberpunk" in raw or "赛博朋克" in raw:
        return "cyberpunk"
    if "realism" in raw or "现实主义" in raw:
        return "realism"
    if "youth" in raw or "coming-of-age" in raw or "青春成长" in raw:
        return "youth_coming_of_age"
    if "general series" in raw or "通用连续剧" in raw:
        return "general_series"
    return "general_series"


_MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE: Dict[str, str] = {
    "trailer": (
        "- 这是预告片，不是正片的一集。不按集推进，不回收上集，不给下集写正片交接。每次新写一条，不改已有预告。\n"
        "- 取材范围以用户提示词为准。写了从第几集到第几集，就只从这一段取样；没写则从头到尾。\n"
        "- 选材重点按故事顺序锁在三段：建置（01–05：Opening、ThemeStated、铺垫、Inciting、Debate）→ 娱乐时间（FunGames）→ 反派逼近（BadGuysCloseIn）。建置含这五拍，不收成只有铺垫。侧重点写了，就在这三段里加重它；没写也是这三段，不改去结局。\n"
        "- 建置按 01 到 05 演开场、主题、处境、催化剂和争执。娱乐时间演冲突怎么升级。反派逼近演压力已经压上来。片段之间用因果接上（因为／于是），没看过正片的观众也能跟上。\n"
        "- 带上基础世界观。世界背景写规则、制度、能力边界里缺了就看不懂选择的那一句。剧情背景写公开处境、关系前史、这场冲突此刻为何非做不可。都用建置里的动作或对白演出来。不把背景句贴成旁白，不借这一拍写出后文终局、最终 Boss 或未揭露的秘密。\n"
        "- 高光剧情是主体，三类都要拍出来：动作（看得见、有结果）、对白（当场说出口，含大纲金句与冲突句）、情节（这一拍改变了什么、下一拍为何接着发生）。娱乐时间落在取材范围内时至少贡献 3 段高光。\n"
        "- 范围内有的建置五拍、娱乐时间和反派逼近都要有落点。落在范围外的不越界去取，也不用结局拍来补。核心看点必须在这些片段里被看见或听见。\n"
        "- 收口停在反派逼近：对手压上来，选择还没做完。不取一无所有、灵魂黑夜、进入终章、终场、终场画面，不演终场选择，隐藏反派不点名。\n"
        "- 结构化预填里的核心建置和人物弧光必须体现。核心建置是概念、思想、对抗、三幕价值方向、故事世界：概念和思想各用一个动作或一句对白，对抗落在娱乐时间并在反派逼近顶一下，价值方向只写范围内各幕往哪边翻，故事世界与世界背景落在建置。人物弧光要读出旧的自己、被逼要改的那一下、以及往哪边走。不另开说明拍，篇幅按 5000 字写，不演谁胜谁负。范围内节拍上针对主控思想、对抗鸿沟危机、价值弧、压力场、人物前提弧光的对话种子，原句入短拍，并写出说者与听者的微动作和表情；自白只写说者。\n"
        "- 5000 字内。高光短拍 10–20 拍。跑、追、飞、掠、行驶的主体仍写从哪到哪、跨距和用时，速度由这两数读出；这段路落在街、路、海、空域、楼缝或航道，不落在驾驶舱。H1 必须是 # 预告-{短题}，短题不超过 8 字，从这段预告的剧情起名，不把侧重点、生成指导或取材范围写进短题。"
    ),
    "short_drama": (
        "- 首分钟强钩子；压缩说明；快反转；集末强悬念；短句对白。\n"
        "- 表演主轴=对白+微表情+微动作（每句台词配说话人/听者微表演，禁对白裸奔）。\n"
        "- 减环境与动作变化：1-2 场、同轴近景、少换锚点/少走位/少道具大交互/少环境奇观；反转靠台词与表情落点而非场面调度。\n"
        "- 优先用有趣、机锋、刻薄、挑衅等有记忆点的短句对白推进关键信息，避免大段旁白式说明。"
    ),
    "feature_film": (
        "- 按电影单集/单部节奏组织起承转合；允许更完整的空间建置与动作链，但仍须服务核心冲突。"
    ),
    "action_feature": (
        "- 目标驱动情节；地理清晰；战术逐步升级；动作后果可见。"
    ),
    "romance_emotional": (
        "- 关系张力优先；多利用停顿/潜台词/身体距离；对白承担关系升降与人物塑形。"
    ),
    "mystery_thriller": (
        "- 精确控制线索；转移怀疑对象；压力逐步升级；结局设揭秘或陷阱。"
    ),
    "comedy_light": (
        "- 节奏性反转；误会成组；喜剧因果清晰。"
    ),
    "xianxia_fantasy": (
        "- 命运秩序与阶层奇观；术法/武戏须写可读动作链与特效层级，禁止只写“打起来”。"
    ),
    "sci_fi_adventure": (
        "- 未知探索；科技具象；逻辑破解；设定自洽。"
    ),
    "period_wuxia": (
        "- 江湖规矩；身法兵器；环境破坏；近身/兵器对抗按起势/换招/受力反馈/结果落位拆写。"
    ),
    "modern_workplace": (
        "- 职级权力；信息差；资源争夺；受限公共空间视线拉扯。"
    ),
    "horror": (
        "- 视觉盲区；生理恐惧；铺垫后惊吓释放。"
    ),
    "cyberpunk": (
        "- 阶级反差；技术异化；入侵/追击时写技术后果可视化与实体动作反馈。"
    ),
    "realism": (
        "- 克制；生活细节；困境与解法扎根现实。"
    ),
    "youth_coming_of_age": (
        "- 自我认同；同辈后果；本集一步成长。"
    ),
    "general_series": (
        "- 铺垫、升级、反转、情感释放、后续价值之间保持平衡。"
    ),
    "emotion_driven": (
        "- 这是情绪驱动类。重点是社会与人性，不是类型奇观。\n"
        "- 结构只按埃格里《编剧的艺术》：前提、三维、统一的对立面、编排、攻击点，然后一阶比一阶更贵，直到危机、带代价的证明和结局。\n"
        "- 剧情由角色冲突的发生和解决推动。抽掉双方不肯让的信念之后，事件仍能当任务发生，这一步就不合格。\n"
        "- 社会层是制度、阶层、舆论。人性层是怕、愧、执念、责任。至少一层必须让这一次选择变贵。只写心情、不发生冲突、不做出选择，不合格。\n"
        "- 本集只演框架已锁的冲突阶，并用该集已锁的故事环步来排。环步必须落在这一阶里。禁止改走救猫咪十五拍，禁止用故事环代替冲突阶。\n"
        "- 框架的经典借鉴只提供整体逻辑。大纲的基本点是本集经典借鉴的最底下一处，必须先落地。可以再加借鉴点，与基本点综合起来实现本集目标。可以参考剧情，必须符合本集背景和主题，按本集因果融合，不能硬拼。\n"
        "- 对白承担冲突：下一句必须顶住、让步，或把代价说出来。情绪写在表情和微动作上，用来让这场冲突被看见。\n"
        "- 解决必须是可见选择，并回指前提。不能用外部事故替人物做完选择。奇观不代替这场解决。"
    ),
    "series_ip": (
        "- 这是系列剧（IP模式）。全剧只提供世界观、主要角色 IP、基本故事线索；没有预先写好的分集剧情框架。\n"
        "- 本集只演用户指定的基本剧情、要体现的冲突和重要亮点。框架经典借鉴只提供整体逻辑。本集指定里的对标是基本点，必须先落地；没有对标就先定一处经典基本点。可以再加借鉴点，综合实现本集指定。符合本集背景和主题后按本集因果融合，不能硬拼，也不整段搬来当本集大纲。\n"
        "- 此前各集摘要是已发生事实，必须承接。不得改人设，不得改世界规则，不得替未写的集编情节。\n"
        "- 正片之外必须写出本集摘要，供下一集读取。"
    ),
}


EMOTION_DRIVEN_STRUCTURE_PROMPT = "emotion_driven_structure_prefill.txt"
EMOTION_DRIVEN_FRAMEWORK_PROMPT = "emotion_driven_story_framework.md"
GLOBAL_STORY_FRAMEWORK_PROMPTS = frozenset({
    "master_story_architect.md",
    EMOTION_DRIVEN_FRAMEWORK_PROMPT,
})


def is_emotion_driven_script_mode(script_mode: Any) -> bool:
    return _normalize_script_mode_key(script_mode) == "emotion_driven"


def resolve_global_story_framework_prompt(script_mode: Any) -> str:
    if is_emotion_driven_script_mode(script_mode):
        return EMOTION_DRIVEN_FRAMEWORK_PROMPT
    return "master_story_architect.md"


def is_global_story_framework_prompt(prompt_filename: Any) -> bool:
    name = str(prompt_filename or "").strip().replace("\\", "/").split("/")[-1]
    return name in GLOBAL_STORY_FRAMEWORK_PROMPTS


def _build_mandatory_writing_logic(script_mode: Any) -> str:
    key = _normalize_script_mode_key(script_mode)
    return _MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE.get(key) or _MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE["general_series"]


def _resolve_episode_duration_minutes(value: Any, *, default: int = 1) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


def build_story_episode_coverage_block(episodes_count: Any) -> str:
    """Restate the per-episode gate next to Episodes Count. Series IP mode must not inject this."""
    try:
        n = int(episodes_count)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    end = f"EP{n:02d}"
    return (
        "【分集完整 — 最高，紧挨集数】\n"
        f"Episodes Count = {n}。§9 逐集输出 EP01–{end}，共 {n} 块；"
        "每集一对 [EPISODE_BLOCK_START:EPxx] / [EPISODE_BLOCK_END:EPxx]，集号连续。\n"
        "每一集只有十行：标题、摘要、交接、时间、救猫咪拍、在场名、AI、专业、驱动、基本点。时间行写明本集范围（绝对，或相对已登记时间节点），并确认季节、昼夜、气候。救猫咪拍确认本集在完成哪一拍，写拍名和收完。AI 行写落到本集这些拍上的优势和回避，没有则写优势=无｜回避=无。专业行写本集碰到的领域，以及这一下的专业动作和专业对白；没碰到写领域=无｜动作=无｜对白=无。驱动行的最大项是角色弧光和冲突；情绪、欲望或外事只写这一下怎么被看见。基本点只写一处经典、一个落点，是这一集借鉴的最底下一处。不写流行，不写第二处。下一集的入就是上一集的出：同一个人、同一处、同一件还在做的事。摘要从这态接着写。要换地方，先写离开和到达。双线或蒙太奇可以切场，交接必须写切=双线或切=蒙太奇，并写明切到哪一条、哪些地方；没写就不是切场。跳=否时，中间不能空出没写的过程。不写故事环、场表、卖点，不把 AI 行写成长文，不把专业行写成百科。已闭合的集不重写。\n"
        "多集合并、只写头尾、或用「同上/略/类推/中后段加快/见大纲」代替任何一集，都要拆回逐集再交。\n"
        "不输出 §0–§8。世界背景、剧情背景、人物、时间节点、专业领域、场景与道具、钩子已经在剧本框架，本阶段不重写，也不另起人物小传。角色名沿用框架。在场名里的环境逐字等于剧本框架场景与道具已登记的空间名，一集可以写多处，不并成一个名字。框架没登记、这一集离了就做不成的地方，改成能站进去的名字并标补=。框架名是事件、争夺、防线、撤离、会面、通路、战略区、通讯区或角色名加会面区时，改成这一处实际地方。不写用户原文保留区，不写逐字落实映射，不回抄用户原文。\n"
        f"收束前点名：[EPISODE_BLOCK_START] 的个数 = {n}。少一块就补上再收束。\n"
    )


def build_emotion_driven_episode_coverage_block(episodes_count: Any) -> str:
    """Per-episode gate for the Egri framework. Does not ask for Save the Cat beats."""
    try:
        n = int(episodes_count)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    end = f"EP{n:02d}"
    return (
        "【分集完整 — 情绪驱动类，最高，紧挨集数】\n"
        f"Episodes Count = {n}。§9 逐集输出 EP01–{end}，共 {n} 块；"
        "每集一对 [EPISODE_BLOCK_START:EPxx] / [EPISODE_BLOCK_END:EPxx]，集号连续。\n"
        "这一档的骨架是埃格里《编剧的艺术》的上升冲突，不是救猫咪。\n"
        "每一集只有十一行：标题、摘要、交接、时间、冲突阶、故事环、在场名、AI、专业、驱动、基本点。"
        "冲突阶确认本集在完成哪一阶，写阶名和收完。阶名只许：攻击点、反攻、锁死、编排、过渡、危机、证明、结局。"
        "故事环确认本集在走哪一步，写环、落阶和人物改了。步名只许：你、需要、出发、寻找、找到、付出、返回、改变。落阶必须等于本集冲突阶。"
        "禁止写成救猫咪拍，禁止写成 Opening、Midpoint、Finale。\n"
        "时间行写明本集范围，并确认季节、昼夜、气候。"
        "AI 行写落到本集这些阶上的优势和回避，没有则写优势=无｜回避=无。"
        "专业行写本集碰到的领域，以及这一下的专业动作和专业对白；没碰到写领域=无｜动作=无｜对白=无。"
        "驱动行的最大项是这一阶的角色弧光和这场冲突；情绪只写这一下怎么被看见。\n"
        "下一集的入就是上一集的出：同一个人、同一处、同一件还在做的事。摘要从这态接着写。要换地方，先写离开和到达。\n"
        "故事环单独成行，不并进冲突阶，也不另写一件事。基本点只写一处经典、一个落点，是这一集借鉴的最底下一处。不写流行，不写第二处。不写场表、卖点。不把冲突阶写成节拍表。已闭合的集不重写。\n"
        "经典借鉴留在剧本框架，本阶段不重写。缩短篇幅时不得改框架。\n"
        "不输出 §0–§8。世界背景、剧情背景和专业领域已经在剧本框架。在场名里的环境逐字等于剧本框架场景与道具已登记的空间名，一集可以写多处。框架没登记的才改成能站进去的名字并标补=。框架名是事件区、通路、会面区、防线时改成这一处实际地方。\n"
        f"收束前点名：[EPISODE_BLOCK_START] 的个数 = {n}。少一块就补上再收束。\n"
    )


def emotion_driven_episode_fill_system() -> str:
    return (
        "你在补全情绪驱动类全局故事框架里缺掉的集。只输出本次点名的集。\n"
        "骨架是埃格里《编剧的艺术》的上升冲突，不是救猫咪。\n"
        "每一集一对独占行 [EPISODE_BLOCK_START:EPxx] 与 [EPISODE_BLOCK_END:EPxx]，集号用两位。\n"
        "每集只有十一行：标题、摘要（因为/所以/但是）、交接（入/出/钩子）、时间（含季节、昼夜、气候）、"
        "冲突阶（阶名和收完）、故事环（环、落阶、人物改了）、在场名、AI、专业、驱动、"
        "基本点（只写一处经典、一个落点，不写流行，不写第二处）。\n"
        "阶名只许攻击点、反攻、锁死、编排、过渡、危机、证明、结局。"
        "环步只许你、需要、出发、寻找、找到、付出、返回、改变，落阶等于本集冲突阶。\n"
        "禁止写成救猫咪拍或 Opening、Midpoint、Finale。不写卖点、场表。驱动的最大项是弧光和冲突。\n"
        "补上的集，入必须接上已有上一集的出。不写思考过程，不重写 §0–§8。\n"
    )


def _build_episode_script_product_specs_block(
    *,
    episodes_count: Any,
    episode_duration_minutes: Any = 1,
    script_mode: str,
    target_audience: str,
) -> str:
    mode_label = script_mode or "（缺失：按项目全局框架与题材常识保守处理）"
    audience_label = target_audience or "（缺失：按项目全局框架与题材常识保守处理）"
    duration_minutes = _resolve_episode_duration_minutes(episode_duration_minutes)
    mandatory_logic = _build_mandatory_writing_logic(script_mode)
    return (
        "Project Product Specs (Hard Constraint):\n"
        f"- 载体规格 / Episodes Count: {episodes_count}\n"
        f"- 每集时长 / Episode Duration: {duration_minutes} minute(s)\n"
        f"- 产品规格与节奏 / Script Mode (Product Format): {mode_label}\n"
        f"- 受众定位 / Target Audience: {audience_label}\n"
        "\n"
        "Script Mode (Hard Constraint):\n"
        f"- {mode_label}\n"
        "\n"
        "Mandatory Writing Logic (强制写作逻辑, Hard Constraint):\n"
        f"{mandatory_logic}\n"
        "- Script Mode 与 Mandatory Writing Logic 为硬性写作逻辑；与通用默认冲突时，以本节为准。\n"
        "- 受众定位须极化核心看点与关系/情绪张力（男频/女频/全受众差异须体现在冲突选择与表达方式上）。\n"
        "\n"
    )


def _log_shot_submit_debug(kind: str, req: Any, refs: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
    if not _is_shot_submit_debug_enabled():
        return
    try:
        final_refs = _normalize_ref_list(refs if refs is not None else getattr(req, "ref_image_url", None))
        payload = {
            "kind": kind,
            "project_id": getattr(req, "project_id", None),
            "shot_id": getattr(req, "shot_id", None),
            "shot_number": getattr(req, "shot_number", None),
            "shot_name": getattr(req, "shot_name", None),
            "asset_type": getattr(req, "asset_type", None),
            "provider": getattr(req, "provider", None),
            "model": getattr(req, "model", None),
            "prompt": str(getattr(req, "prompt", "") or ""),
            "prompt_len": len(str(getattr(req, "prompt", "") or "")),
            "ref_count": len(final_refs),
            "refs": final_refs,
            "ref_names": _build_ref_display_names(final_refs),
        }
        if extra:
            payload.update(extra)
        llm_service.log_audit("SHOT_SUBMIT_DEBUG", payload)
    except Exception as exc:
        logger.warning("[ShotSubmitDebug] failed to log payload: %s", exc)



# datetime/compact -> generation_runtime.job_store