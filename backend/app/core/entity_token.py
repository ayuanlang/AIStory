import re
from typing import Any, List

_TYPED_ENTITY_REF_RE = re.compile(
    r"CHAR\s*:\s*\[@([^\]]+)\]|ENV\s*:\s*\[([^\]]+)\]|PROP\s*:\s*\[([^\]]+)\]",
    flags=re.IGNORECASE,
)


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


def subject_compare_key(value: Any) -> str:
    """Compact key for matching scene subject references to entity names."""
    text = normalize_entity_token(value)
    if not text:
        return ""
    text = re.sub(r"^(?:char|prop|env|extra|cover)\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    text = text.lstrip("@").strip()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = normalize_entity_token(text)
    text = re.sub(r"[\s_\-]+", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    return text


def subject_compare_key_variants(value: Any) -> set:
    """Return compare keys including a base form without parenthetical aliases."""
    variants: set = set()
    primary = subject_compare_key(value)
    if primary:
        variants.add(primary)

    raw = str(value or "").strip()
    if not raw:
        return variants

    normalized = normalize_entity_token(raw)
    normalized = re.sub(r"^(?:char|prop|env|extra|cover)\s*:\s*", "", normalized, flags=re.IGNORECASE).strip()
    normalized = re.sub(r"^[\[\{\(]+|[\]\}\)]+$", "", normalized).lstrip("@").strip()
    base = re.sub(r"\([^)]*\)", "", normalized).strip()
    base_key = subject_compare_key(base)
    if base_key:
        variants.add(base_key)
    return variants


def extract_typed_entity_raw_names(text: Any) -> List[str]:
    """Extract entity names from typed CHAR/ENV/PROP references in prompt text."""
    source = str(text or "")
    if not source:
        return []

    names: List[str] = []
    for match in _TYPED_ENTITY_REF_RE.finditer(source):
        name = (match.group(1) or match.group(2) or match.group(3) or "").strip()
        if name:
            names.append(name)
    return names


def _is_polluted_entity_capture(name: str) -> bool:
    """Skip brace captures that include typed tags plus action prose."""
    text = str(name or "").strip()
    if not text:
        return True
    if re.search(r"^(CHAR|ENV|PROP)\s*:\s*\[[^\]]+\]\s+\S", text, flags=re.IGNORECASE):
        return True
    if len(text) > 80:
        return True
    return False


def extract_entity_raw_names_from_prompt(text: Any) -> List[str]:
    """Extract entity name candidates from typed refs plus bracket/@ tokens."""
    source = str(text or "")
    if not source:
        return []

    raw_names: List[str] = []
    raw_names.extend(extract_typed_entity_raw_names(source))

    for pattern in (
        r"\[([\s\S]+?)\]",
        r"\{([\s\S]+?)\}",
        r"【([\s\S]+?)】",
        r"｛([\s\S]+?)｝",
    ):
        for match in re.finditer(pattern, source):
            captured = str(match.group(1) or "").strip()
            if captured and not _is_polluted_entity_capture(captured):
                raw_names.append(captured)

    for match in re.finditer(
        r"(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)",
        source,
    ):
        raw_names.append(str(match.group(1) or "").strip())

    seen: set[str] = set()
    unique: List[str] = []
    for name in raw_names:
        key = normalize_entity_token(name)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(name)
    return unique


def entity_subject_keys_match(entity_keys: set, candidate_keys: set) -> bool:
    if not entity_keys or not candidate_keys:
        return False
    if entity_keys.intersection(candidate_keys):
        return True
    for entity_key in entity_keys:
        if not entity_key or len(entity_key) < 2:
            continue
        for candidate_key in candidate_keys:
            if not candidate_key:
                continue
            if entity_key in candidate_key or candidate_key in entity_key:
                return True
    return False
