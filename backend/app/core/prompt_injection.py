from __future__ import annotations

import re
from typing import Optional

START = "\u5f00\u59cb"
END = "\u7ed3\u675f"


def wrap_injection_section(label: str, content: str) -> str:
    body = str(content or "").strip()
    if not body:
        return ""
    start_tag = f"[{label}{START}]"
    end_tag = f"[{label}{END}]"
    return f"{start_tag}\n{body}\n{end_tag}"


def unwrap_injection_section(text: str, label: str) -> Optional[str]:
    pattern = rf"\[{re.escape(label)}{START}\]\s*(.*?)\s*\[{re.escape(label)}{END}\]"
    match = re.search(pattern, str(text or ""), flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def strip_injection_section(text: str, label: str) -> str:
    pattern = rf"\[{re.escape(label)}{START}\]\s*.*?\s*\[{re.escape(label)}{END}\]\s*"
    return re.sub(pattern, "", str(text or ""), flags=re.DOTALL).strip()
