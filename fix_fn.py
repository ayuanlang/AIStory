def run():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    part1 = '    return _dedupe_media_ref_urls(auto_entity_refs), auto_entity_refs'
    part2 = '        image_url = str(row.get("image_url")'

    idx1 = text.find(part1)
    if idx1 == -1: 
        print("part1 not found")
        return
    idx2 = text.find(part2, idx1)
    if idx2 == -1 or idx2 - idx1 > 200: 
        print("part2 not found or too far")
        return

    old_code = text[idx1:idx2] + part2

    new_code = part1 + '''

def _compute_subject_ref_index_map(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    text = str(prompt or "")
    if not text:
        return {}

    refs: List[str] = []
    index_map: Dict[str, int] = {}
    import re
    # We use u3010 and u3011 for chinese brackets 【】
    regex = re.compile(r"(?:CHAR|ENV|PROP)?\s*:\s*[\[\u3010](.*?)[\]\u3011]|[\[\u3010](.*?)[\]\u3011]", re.IGNORECASE)

    for m in regex.finditer(text):
        raw_name = m.group(1) or m.group(2) or ""
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue

        row = entity_lookup.get(normalized)
        if not row:
            continue

        entity_type = str(row.get("entity_type") or "").strip().lower()
        if entity_type not in {"subject", "character", "char"}:
            continue

''' + part2

    new_text = text.replace(old_code, new_code)
    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Fixed function injection!")

run()