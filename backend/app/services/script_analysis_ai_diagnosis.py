"""Build prompts and truncate payloads for page AI diagnosis (script analysis / assets)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

OPS_SUPPORT_EMAIL = "metawave@126.com"

_MAX_MANUAL_CHARS = 36000
_MAX_LOGS_CHARS = 24000
_MAX_WORKSPACE_CHARS = 36000
_MAX_NOTE_CHARS = 4000
_MAX_HISTORY_TURNS = 20
_MAX_HISTORY_MSG_CHARS = 8000

_PAGE_SCOPE_SCRIPT = "script_analysis"
_PAGE_SCOPE_ASSETS = "assets"


def normalize_page_scope(page_scope: Any = None) -> str:
    raw = str(page_scope or _PAGE_SCOPE_SCRIPT).strip().lower()
    if raw in {_PAGE_SCOPE_ASSETS, "asset", "subject", "subjects", "subject_library"}:
        return _PAGE_SCOPE_ASSETS
    return _PAGE_SCOPE_SCRIPT


def _clip(text: Any, max_chars: int) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars:
        return raw
    keep = max(0, max_chars - 80)
    return f"{raw[:keep]}\n\n…（内容过长，已截断，共 {len(raw)} 字）"


def _normalize_history(history: Optional[List[Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in list(history or [])[-_MAX_HISTORY_TURNS:]:
        if isinstance(item, dict):
            role = str(item.get("role") or "").strip().lower()
            content = _clip(item.get("content"), _MAX_HISTORY_MSG_CHARS)
        else:
            role = str(getattr(item, "role", "") or "").strip().lower()
            content = _clip(getattr(item, "content", ""), _MAX_HISTORY_MSG_CHARS)
        if role not in {"user", "assistant"} or not content:
            continue
        rows.append({"role": role, "content": content})
    return rows


def _system_prompt_for_scope(page_scope: str) -> str:
    if page_scope == _PAGE_SCOPE_ASSETS:
        return (
            "你是 AI Story 产品的「资产页」操作诊断 Agent。"
            "你以多轮对话方式协助用户：先结合上下文诊断，再回答追问、澄清与细化操作步骤。"
            "用户会提供：资产页操作手册、系统日志、当前资产工作区状态，以及对话历史。"
            "请用简洁、日常的中文交流，面向非技术人员。"
            "\n\n首轮或用户明确要求完整诊断时，优先使用以下结构："
            "\n## 当前状态判断"
            "\n## 可能卡在哪里"
            "\n## 建议下一步（按优先级，3～7 条，可执行）"
            "\n## 需要注意"
            "\n\n后续追问可直接针对性回答，不必每次重复完整四段结构；仍保持可执行、可核对。"
            "\n\n规则："
            "\n- 结合操作手册：先确认清单与类型，再单个试生成，再批量生图；衍生资产先生成依赖源。"
            "\n- 分集继承：资产按分集存储；新集入库会建本集新卡片并可能挂旧集参考，但不会自动拷贝旧图——"
            "要长得像旧集需在资产页「复用资产」/素材库选用旧图，或重新生图；「从源实体同步」只同步文字不同步图。"
            "\n- 缺卡片（名单都没有）→ 回剧本分析进度诊断面板，对「资产设计」做「资产生成重跑」"
            "（全部/分类/单实体），不要指望资产页「新增资产」代替整类设计；有卡片没图才在资产页生图。"
            "\n- 生图接口优选：日常优先 gpt-Image-2，候补 banana 系列；"
            "遇血腥、暴力、儿童等相关合规拦截时改试 Flux、Doubao 等，再对失败项单独重试。"
            "\n- 强调：批量前确认范围是「当前分集」还是「整个项目」；删除/全量操作前再核对范围。"
            "\n- 依赖未齐套时会跳过或效果不稳；应先补齐依赖图，再生成衍生角色/环境/道具/海报。"
            "\n- 不要编造用户没提供的数据；信息不足就明确说还缺什么，并可追问。"
            "\n- 不要输出内部字段名（如 Subject Index、entity_design JSON、API 路径等），改用业务说法。"
            "\n- 你只给操作建议，不会也不能直接改用户工作区内容。"
        )

    return (
        "你是 AI Story 产品的「剧本分析页」操作诊断 Agent。"
        "你以多轮对话方式协助用户：先结合上下文诊断，再回答追问、澄清与细化操作步骤。"
        "用户会提供：操作手册、系统日志、当前本集工作区状态，以及对话历史。"
        "请用简洁、日常的中文交流，面向非技术人员。"
        "\n\n首轮或用户明确要求完整诊断时，优先使用以下结构："
        "\n## 当前状态判断"
        "\n## 可能卡在哪里"
        "\n## 建议下一步（按优先级，3～7 条，可执行）"
        "\n## 需要注意"
        "\n\n后续追问可直接针对性回答，不必每次重复完整四段结构；仍保持可执行、可核对。"
        "\n\n规则："
        "\n- 结合当前流程：场景拆分 → 环境逐场程序回填 →（资产清单 ∥ 逐场文戏/特效/仙攻/建置优化）→（场景编排 ∥ 资产设计）→ 分镜；分镜须等待场景编排与环境资产设计，核对以本集齐套为准。"
        "\n- 强调：上环节改了，下环节要重跑才生效；重跑前先删旧内容，系统不会自动覆盖已生成内容。"
        "\n- 场景编排是为了工程化管理剧本，便于分场管理与自动识别资产，不是改故事。"
        "\n- 不要编造用户没提供的数据；信息不足就明确说还缺什么，并可追问。"
        "\n- 不要输出内部字段名（如 Subject Index、Stage 2.1、JSON API 等），改用业务说法。"
        "\n- 你只给操作建议，不会也不能直接改用户工作区内容。"
    )


def build_diagnosis_messages(
    *,
    manual_text: str = "",
    system_logs: str = "",
    workspace_summary: str = "",
    user_note: str = "",
    history: Optional[List[Any]] = None,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    episode_label: str = "",
    page_scope: Any = None,
) -> Tuple[list, Dict[str, Any]]:
    scope = normalize_page_scope(page_scope)
    manual = _clip(manual_text, _MAX_MANUAL_CHARS)
    logs = _clip(system_logs, _MAX_LOGS_CHARS)
    workspace = _clip(workspace_summary, _MAX_WORKSPACE_CHARS)
    note = _clip(user_note, _MAX_NOTE_CHARS)
    turns = _normalize_history(history)

    manual_heading = "# 操作手册（资产页）" if scope == _PAGE_SCOPE_ASSETS else "# 操作手册（剧本分析）"
    workspace_heading = "# 资产工作区概况" if scope == _PAGE_SCOPE_ASSETS else "# 本集工作区概况"
    ready_reply = (
        "已收到资产页操作手册、系统日志与工作区概况。"
        "请直接描述你遇到的问题，或继续追问；我会按对话给出可执行建议。"
        if scope == _PAGE_SCOPE_ASSETS
        else (
            "已收到本集操作手册、系统日志与工作区概况。"
            "请直接描述你遇到的问题，或继续追问；我会按对话给出可执行建议。"
        )
    )

    context_parts = [
        "# 诊断上下文（本会话固定参考，请始终结合）",
        f"- 诊断页面：{'资产页' if scope == _PAGE_SCOPE_ASSETS else '剧本分析页'}",
        f"- 项目 ID：{project_id if project_id is not None else '未知'}",
        f"- 分集 ID：{episode_id if episode_id is not None else '未知'}",
        f"- 分集：{episode_label or '未命名'}",
        "",
        manual_heading,
        manual or "（未提供）",
        "",
        "# 系统日志（最近）",
        logs or "（暂无）",
        "",
        workspace_heading,
        workspace or "（未提供）",
    ]

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _system_prompt_for_scope(scope)},
        {"role": "user", "content": "\n".join(context_parts)},
        {
            "role": "assistant",
            "content": ready_reply,
        },
    ]

    if turns:
        # History from the client already includes the latest user turn.
        messages.extend(turns)
    elif note:
        messages.append({"role": "user", "content": note})
    else:
        messages.append(
            {
                "role": "user",
                "content": "当前有什么问题，下一步该怎么办",
            }
        )

    meta = {
        "manual_chars": len(manual),
        "logs_chars": len(logs),
        "workspace_chars": len(workspace),
        "note_chars": len(note),
        "history_turns": len(turns),
        "ops_email": OPS_SUPPORT_EMAIL,
        "agent_mode": True,
        "page_scope": scope,
    }
    return messages, meta


def format_conversation_transcript(history: Optional[List[Any]], user_note: str = "", advice: str = "") -> str:
    turns = _normalize_history(history)
    if not turns:
        parts = []
        note = _clip(user_note, _MAX_NOTE_CHARS)
        if note:
            parts.append(f"用户：{note}")
        if advice:
            parts.append(f"助手：{_clip(advice, 20000)}")
        return "\n\n".join(parts) if parts else "（无）"

    lines: List[str] = []
    for turn in turns:
        label = "用户" if turn["role"] == "user" else "助手"
        lines.append(f"{label}：{turn['content']}")
    if advice and (not turns or turns[-1].get("role") != "assistant" or turns[-1].get("content") != advice):
        lines.append(f"助手：{_clip(advice, 20000)}")
    return "\n\n".join(lines)


def build_ops_email_body(
    *,
    username: str,
    user_email: str,
    project_id: Optional[int],
    episode_id: Optional[int],
    episode_label: str,
    user_note: str,
    advice: str,
    manual_text: str,
    system_logs: str,
    workspace_summary: str,
    history: Optional[List[Any]] = None,
    page_scope: Any = None,
) -> Tuple[str, str]:
    scope = normalize_page_scope(page_scope)
    page_label = "资产页" if scope == _PAGE_SCOPE_ASSETS else "剧本分析页"
    subject = (
        f"[AI Story {page_label}诊断] "
        f"user={username or 'unknown'} "
        f"project={project_id or '-'} episode={episode_id or '-'}"
    )
    transcript = format_conversation_transcript(history, user_note=user_note, advice=advice)
    content = "\n".join(
        [
            f"AI Story · {page_label} AI 诊断工单（Agent 对话）",
            "",
            f"用户：{username or 'unknown'}",
            f"用户邮箱：{user_email or '未填写'}",
            f"项目 ID：{project_id if project_id is not None else '-'}",
            f"分集 ID：{episode_id if episode_id is not None else '-'}",
            f"分集：{episode_label or '未命名'}",
            "",
            "===== 对话记录 =====",
            transcript,
            "",
            "===== 最近一条 AI 建议 =====",
            _clip(advice, 20000) or "（空）",
            "",
            "===== 工作区概况 =====",
            _clip(workspace_summary, 12000) or "（空）",
            "",
            "===== 系统日志（节选） =====",
            _clip(system_logs, 12000) or "（空）",
            "",
            "===== 操作手册（节选） =====",
            _clip(manual_text, 8000) or "（空）",
        ]
    )
    return subject, content
