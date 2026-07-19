"""Build prompts and truncate payloads for script-page AI diagnosis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

OPS_SUPPORT_EMAIL = "metawave@126.com"

_MAX_MANUAL_CHARS = 36000
_MAX_LOGS_CHARS = 24000
_MAX_WORKSPACE_CHARS = 36000
_MAX_NOTE_CHARS = 4000
_MAX_HISTORY_TURNS = 20
_MAX_HISTORY_MSG_CHARS = 8000


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
) -> Tuple[list, Dict[str, Any]]:
    manual = _clip(manual_text, _MAX_MANUAL_CHARS)
    logs = _clip(system_logs, _MAX_LOGS_CHARS)
    workspace = _clip(workspace_summary, _MAX_WORKSPACE_CHARS)
    note = _clip(user_note, _MAX_NOTE_CHARS)
    turns = _normalize_history(history)

    system_prompt = (
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
        "\n- 结合操作手册里的流程：剧本统筹 → 资产清单 → 场景编排∥资产设计 → 分镜；核对以本集齐套为准。"
        "\n- 强调：上环节改了，下环节要重跑才生效；重跑前先删旧内容，系统不会自动覆盖已生成内容。"
        "\n- 场景编排是为了工程化管理剧本，便于分场管理与自动识别资产，不是改故事。"
        "\n- 不要编造用户没提供的数据；信息不足就明确说还缺什么，并可追问。"
        "\n- 不要输出内部字段名（如 Subject Index、Stage 2.1、JSON API 等），改用业务说法。"
        "\n- 你只给操作建议，不会也不能直接改用户工作区内容。"
    )

    context_parts = [
        "# 诊断上下文（本会话固定参考，请始终结合）",
        f"- 项目 ID：{project_id if project_id is not None else '未知'}",
        f"- 分集 ID：{episode_id if episode_id is not None else '未知'}",
        f"- 分集：{episode_label or '未命名'}",
        "",
        "# 操作手册（剧本分析）",
        manual or "（未提供）",
        "",
        "# 系统日志（最近）",
        logs or "（暂无）",
        "",
        "# 本集工作区概况",
        workspace or "（未提供）",
    ]

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(context_parts)},
        {
            "role": "assistant",
            "content": (
                "已收到本集操作手册、系统日志与工作区概况。"
                "请直接描述你遇到的问题，或继续追问；我会按对话给出可执行建议。"
            ),
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
                "content": "请基于以上信息，先判断当前可能卡在哪里，并给出建议下一步。",
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
) -> Tuple[str, str]:
    subject = (
        f"[AI Story 剧本分析诊断] "
        f"user={username or 'unknown'} "
        f"project={project_id or '-'} episode={episode_id or '-'}"
    )
    transcript = format_conversation_transcript(history, user_note=user_note, advice=advice)
    content = "\n".join(
        [
            "AI Story · 剧本分析页 AI 诊断工单（Agent 对话）",
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
            "===== 本集工作区概况 =====",
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
