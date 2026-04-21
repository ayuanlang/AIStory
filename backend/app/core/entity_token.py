import re
from typing import Any


def _normalize_ascii_word_separators(value: str) -> str:
    return re.sub(
        r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+",
        lambda match: re.sub(r"[_-]+", " ", match.group(0)),
        value,
    )


def normalize_entity_token(value: Any) -> str:
    text = str(value or "")
    text = (
        text.replace("（", "(")
        .replace("）", ")")
        .replace("【", "[")
        .replace("】", "]")
        .replace("〔", "[")
        .replace("〕", "]")
        .replace("［", "[")
        .replace("］", "]")
        .replace("‘", "")
        .replace("’", "")
        .replace("“", "")
        .replace("”", "")
        .replace('"', "")
        .replace("'", "")
        .replace("`", "")
    )
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text).strip()

    text = re.sub(r"^(CHAR|ENV|PROP|VEFX|SFX)\s*:\s*", "", text, flags=re.IGNORECASE).strip()

    for _ in range(3):
        next_text = re.sub(r"^[\[\{\(\s]+|[\]\}\)\s]+$", "", text)
        next_text = re.sub(r"^@+", "", next_text).strip()
        if next_text == text:
            break
        text = next_text

    text = re.sub(r"\s+", " ", _normalize_ascii_word_separators(text)).strip()

    return text.lower()
