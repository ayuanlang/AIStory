import re

def main():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Update signature
    old_sig = '''def _append_video_api_ref_mapping(
    prompt: str,
    refs: List[str],
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    keyframes: Optional[List[str]] = None,
    reference_video_urls: Optional[List[str]] = None,
) -> str:'''
    new_sig = '''def _append_video_api_ref_mapping(
    prompt: str,
    refs: List[str],
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    keyframes: Optional[List[str]] = None,
    reference_video_urls: Optional[List[str]] = None,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:'''
    text = text.replace(old_sig, new_sig, 1)

    # 2. Update logic: Wait, we will find `image_slots = [x for x in dict.fromkeys(image_slots) if x]` 
    # and replace downwards unit the `if mapping_line in text:` block.
    
    old_block = '''    image_slots = [x for x in dict.fromkeys(image_slots) if x]
    video_slots = [f"视频{i + 1}" for i, v in enumerate(reference_video_urls or []) if str(v).strip()]
    media_slots = image_slots + video_slots
    if not media_slots:
        return text

    regex = re.compile(r"(?:CHAR|ENV|PROP)?\s*:\s*[\[【](.*?)[\]】]|[\[【](.*?)[\]】]", re.IGNORECASE)
    entity_tokens: List[str] = []
    seen_entities: set[str] = set()
    for m in regex.finditer(text):
        raw_name = m.group(1) or m.group(2) or ""
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized or normalized in seen_entities:
            continue
        seen_entities.add(normalized)
        entity_name = str(raw_name or "").strip()
        if not entity_name:
            continue
        token_text = str(m.group(0) or "")
        token_upper = token_text.upper()
        if token_upper.startswith("CHAR"):
            display = f"CHAR:[@{entity_name}]"
        elif token_upper.startswith("PROP"):
            display = f"PROP:[{entity_name}]"
        elif token_upper.startswith("ENV"):
            display = f"ENV:[{entity_name}]"
        else:
            display = f"[{entity_name}]"
        entity_tokens.append(display)

    if not entity_tokens:
        return text

    pairs: List[str] = []
    for idx, entity_token in enumerate(entity_tokens):
        if idx >= len(media_slots):
            break
        pairs.append(f"{entity_token}->{media_slots[idx]}")

    if not pairs:
        return text

    mapping_line = "实体参考映射: " + "; ".join(pairs)
    if mapping_line in text:
        return text'''

    new_block = '''    image_slots = [x for x in dict.fromkeys(image_slots) if x]
    video_slots = [f"视频{i + 1}" for i, v in enumerate(reference_video_urls or []) if str(v).strip()]
    media_slots = image_slots + video_slots

    pairs: List[str] = []

    # First, always show explicit start/end images if they are mapped and if desired?
    # Usually this is primarily for mapping entities to reference images for API consumption.

    seen_urls: set[str] = set()

    normalized_text = _normalize_entity_anchor_token(text)
    if entity_lookup:
        # Relaxed matching to map any entity in ordered_refs
        for key, row in entity_lookup.items():
            norm_key = str(key or "").strip()
            if not norm_key: continue
            
            allowed_types = {"subject", "character", "char", "environment", "env", "prop", "props"}
            entity_type = str(row.get("entity_type") or "").strip().lower()
            if entity_type and entity_type not in allowed_types:
                continue

            image_url = str(row.get("image_url") or "").strip()
            if not image_url or image_url not in index_map:
                continue

            has_ascii = bool(re.search(r"[a-z0-9]", norm_key, flags=re.IGNORECASE))
            if has_ascii:
                pattern = rf"(?<![a-z0-9]){re.escape(norm_key)}(?![a-z0-9])"
                matched = re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None
            else:
                matched = norm_key in normalized_text
            
            if matched and image_url not in seen_urls:
                seen_urls.add(image_url)
                display_type = "CHAR" if entity_type in {"subject", "character", "char"} else ("ENV" if "env" in entity_type else "PROP")
                display = f"{display_type}:[@{row.get('name')}]" if display_type == "CHAR" else f"{display_type}:[{row.get('name')}]"
                pairs.append(f"{display}->图{index_map[image_url]}")

    # Fallback to pure bracket Regex for ones that might not be in lookup
    regex = re.compile(r"(?:CHAR|ENV|PROP)?\s*:\s*[\[【](.*?)[\]】]|[\[【](.*?)[\]】]", re.IGNORECASE)
    for m in regex.finditer(text):
        raw_name = m.group(1) or m.group(2) or ""
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized: continue
        
        # If it was matched, verify if we can assign an image?
        # But if it wasn't in entity_lookup with a valid URL, what media_slot should we give it?
        # Old code blindly mapped them 1-to-1 with media_slots.
        pass

    if not pairs:
        return text

    mapping_line = "实体参考图映射: " + "; ".join(pairs)
    if mapping_line in text:
        return text'''

    text = text.replace(old_block, new_block, 1)

    # 3. Update the `prompt_text = _append_video_api_ref_mapping` in `_run_generate_video`
    old_call1 = '''        prompt_text = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.ref_image_url,
            req.last_frame_url,
            req.keyframes,
            req.ref_video_urls,
        )'''
    new_call1 = '''        entity_lookup = _build_project_entity_lookup(db, req.project_id) if hasattr(req, 'project_id') and req.project_id else {}
        prompt_text = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.ref_image_url,
            req.last_frame_url,
            req.keyframes,
            req.ref_video_urls,
            entity_lookup=entity_lookup,
        )'''
    text = text.replace(old_call1, new_call1, 1)

    # 4. Update the `_append_video_api_ref_mapping` calls in `shot_media_batch`
    old_call2 = '''            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
            )'''
    new_call2 = '''            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
                entity_lookup=entity_lookup,
            )'''
    text = text.replace(old_call2, new_call2, 1)
    
    old_call3 = '''        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
        )'''
    new_call3 = '''        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            entity_lookup=entity_lookup,
        )'''
    text = text.replace(old_call3, new_call3, 1)
    
    old_call4 = '''                            video_prompt_cn = _append_video_api_ref_mapping(
                                video_prompt_cn,
                                ordered_video_refs,
                                normalized_refs,
                                normalized_last_frame_url,
                                None,
                            )'''
    new_call4 = '''                            video_prompt_cn = _append_video_api_ref_mapping(
                                video_prompt_cn,
                                ordered_video_refs,
                                normalized_refs,
                                normalized_last_frame_url,
                                None,
                                entity_lookup=entity_lookup,
                            )'''
    text = text.replace(old_call4, new_call4, 1)

    old_call5 = '''                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                        )'''
    new_call5 = '''                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                            entity_lookup=entity_lookup,
                        )'''
    text = text.replace(old_call5, new_call5, 1)

    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()
