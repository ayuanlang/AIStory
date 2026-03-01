import re
from typing import Any


def normalize_entity_token(value: Any) -> str:
    text = str(value or "")
    text = (
        text.replace("（", "(")
        .replace("）", ")")
        .replace("【", "[")
        .replace("】", "]")
        .replace("‘", "")
        .replace("’", "")
        .replace("“", "")
        .replace("”", "")
        .replace('"', "")
        .replace("'", "")
        .replace("`", "")
    )
    text = re.sub(r"\s+", " ", text).strip()

    text = re.sub(r"^(CHAR|ENV|PROP)\s*:\s*", "", text, flags=re.IGNORECASE).strip()

    for _ in range(3):
        next_text = re.sub(r"^[\[\{\(\s]+|[\]\}\)\s]+$", "", text)
        next_text = re.sub(r"^@+", "", next_text).strip()
        if next_text == text:
            break
        text = next_text

    return text.lower()
