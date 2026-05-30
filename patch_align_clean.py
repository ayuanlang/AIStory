import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

helper = '''def _extract_frontend_aligned_entity_raw_names(text: str) -> list[str]:
    raw_names = []
    for p in [r"\\[([\\s\\S]+?)\\]", r"\\{([\\s\\S]+?)\\}", r"【([\\s\\S]+?)】", r"｛([\\s\\S]+?)｝"]:
        for m in re.finditer(p, text):
            raw_names.append(m.group(1))
    for m in re.finditer(r"(?:^|[\\s,，;；])(@[^\\s,，;；\\]\\[\\(\\)（）\\{\\}【】]+)", text):
        raw_names.append(m.group(1))
    return raw_names

def _collect_prompt_entity_ref_images('''

if '_extract_frontend_aligned_entity_raw_names' not in text:
    text = text.replace('def _collect_prompt_entity_ref_images(', helper)

old_1 = '''    regex = re.compile(r"(?:CHAR|ENV|PROP|VEFX|SFX)?\\s*:\\s*[\\[【](.*?)[\]】]|[\\[【](.*?)[\]】]", re.IGNORECASE)
    for m in regex.finditer(text):
        raw_name = m.group(1) or m.group(2) or ""
        normalized = _normalize_entity_anchor_token(raw_name)'''

new_1 = '''    raw_names = _extract_frontend_aligned_entity_raw_names(text)
    for raw_name in raw_names:
        normalized = _normalize_entity_anchor_token(raw_name)'''

text = text.replace(old_1, new_1)

old_2 = '''    import re
    # We use u3010 and u3011 for chinese brackets 【】
    regex = re.compile(r"(?:CHAR|ENV|PROP|VEFX|SFX)?\\s*:\\s*[\\[【](.*?)[\]】]|[\\[【](.*?)[\]】]", re.IGNORECASE)

    for m in regex.finditer(text):
        raw_name = m.group(1) or m.group(2) or ""
        normalized = _normalize_entity_anchor_token(raw_name)'''

text = text.replace(old_2, new_1)

old_3 = '''        mention_regex = re.compile(
            r"(?:CHAR|ENV|PROP)\\s*:\\s*[\\[【]\\s*@?([^\\]】]+?)\\s*[\\]】]|[\\[【]\\s*@?([^\\]】]+?)\\s*[\\]】]",
            re.IGNORECASE,
        )

        for match in mention_regex.finditer(source_text):
            raw_name = str(match.group(1) or match.group(2) or "").strip()
            normalized = _normalize_entity_anchor_token(raw_name)'''

new_3 = '''        raw_names = _extract_frontend_aligned_entity_raw_names(source_text)
        for raw_name in raw_names:
            raw_name = str(raw_name or "").strip()
            normalized = _normalize_entity_anchor_token(raw_name)'''

text = text.replace(old_3, new_3)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
