# -*- coding: utf-8 -*-
"""Label a failed skill's unfinished output when it is sent back for continuation."""
from __future__ import annotations


def previous_output_notice(*, detail: str = "") -> str:
    """Tell the model the following block is its own unfinished output, not new input."""
    lines = [
        "【上次输出】",
        "下面这一段是上一次失败时没写完的输出，不是本次输入。",
        "不要把它当成剧本、场次、任务或新材料来读。",
        "从这段输出的最后一个字接着往下写，只补还没写完的部分。",
        "不要重写已有输出，不要重复已有输出，只返回续写。",
    ]
    extra = str(detail or "").strip()
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def append_previous_output(prompt: str, previous_output: str, *, detail: str = "") -> str:
    """Append a clearly labeled previous output after the real task prompt."""
    body = str(previous_output or "").rstrip()
    base = str(prompt or "").rstrip()
    return f"{base}\n\n{previous_output_notice(detail=detail)}\n\n上次输出：\n{body}\n"
