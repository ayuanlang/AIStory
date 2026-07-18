"""Build prompts and truncate payloads for script-page AI diagnosis."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

OPS_SUPPORT_EMAIL = "metawave@126.com"

_MAX_MANUAL_CHARS = 36000
_MAX_LOGS_CHARS = 24000
_MAX_WORKSPACE_CHARS = 36000
_MAX_NOTE_CHARS = 4000


def _clip(text: Any, max_chars: int) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars:
        return raw
    keep = max(0, max_chars - 80)
    return f"{raw[:keep]}\n\n…（内容过长，已截断，共 {len(raw)} 字）"


def build_diagnosis_messages(
    *,
    manual_text: str = "",
    system_logs: str = "",
    workspace_summary: str = "",
    user_note: str = "",
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    episode_label: str = "",
) -> Tuple[list, Dict[str, Any]]:
    manual = _clip(manual_text, _MAX_MANUAL_CHARS)
    logs = _clip(system_logs, _MAX_LOGS_CHARS)
    workspace = _clip(workspace_summary, _MAX_WORKSPACE_CHARS)
    note = _clip(user_note, _MAX_NOTE_CHARS)

    system_prompt = (
        "你是 AI Story 产品的「剧本分析页」操作诊断助手。"
        "用户会提供：操作手册摘要、系统日志、当前本集工作区状态，以及可选补充说明。"
        "请用简洁、日常的中文给出诊断，面向非技术人员。"
        "\n\n输出结构（必须使用以下小标题）："
        "\n## 当前状态判断"
        "\n## 可能卡在哪里"
        "\n## 建议下一步（按优先级，3～7 条，可执行）"
        "\n## 需要注意"
        "\n\n规则："
        "\n- 结合操作手册里的流程：剧本统筹 → 资产清单 → 场景编排∥资产设计 → 分镜；核对以本集齐套为准。"
        "\n- 强调：上环节改了，下环节要重跑才生效；重跑前先删旧内容，系统不会自动覆盖已生成内容。"
        "\n- 场景编排是为了工程化管理剧本，便于分场管理与自动识别资产，不是改故事。"
        "\n- 不要编造用户没提供的数据；信息不足就明确说还缺什么。"
        "\n- 不要输出内部字段名（如 Subject Index、Stage 2.1、JSON API 等），改用业务说法。"
    )

    user_parts = [
        "# 诊断上下文",
        f"- 项目 ID：{project_id if project_id is not None else '未知'}",
        f"- 分集 ID：{episode_id if episode_id is not None else '未知'}",
        f"- 分集：{episode_label or '未命名'}",
        "",
        "# 用户补充说明",
        note or "（无）",
        "",
        "# 操作手册（剧本分析）",
        manual or "（未提供）",
        "",
        "# 系统日志（最近）",
        logs or "（暂无）",
        "",
        "# 本集工作区概况",
        workspace or "（未提供）",
        "",
        "请基于以上信息给出下一步操作建议。",
    ]

    meta = {
        "manual_chars": len(manual),
        "logs_chars": len(logs),
        "workspace_chars": len(workspace),
        "note_chars": len(note),
        "ops_email": OPS_SUPPORT_EMAIL,
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
    return messages, meta


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
) -> Tuple[str, str]:
    subject = (
        f"[AI Story 剧本分析诊断] "
        f"user={username or 'unknown'} "
        f"project={project_id or '-'} episode={episode_id or '-'}"
    )
    content = "\n".join(
        [
            "AI Story · 剧本分析页 AI 诊断工单",
            "",
            f"用户：{username or 'unknown'}",
            f"用户邮箱：{user_email or '未填写'}",
            f"项目 ID：{project_id if project_id is not None else '-'}",
            f"分集 ID：{episode_id if episode_id is not None else '-'}",
            f"分集：{episode_label or '未命名'}",
            "",
            "===== 用户补充说明 =====",
            _clip(user_note, _MAX_NOTE_CHARS) or "（无）",
            "",
            "===== AI 诊断建议 =====",
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
