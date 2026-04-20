import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = """        entity_lookup = _build_project_entity_lookup(db, req.project_id) if hasattr(req, 'project_id') and req.project_id else {}
        prompt_text = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.ref_image_url,
            req.last_frame_url,
            req.keyframes,
            req.ref_video_urls,
            entity_lookup=entity_lookup,
        )"""

new_block = """        entity_lookup = _build_project_entity_lookup(db, req.project_id) if hasattr(req, 'project_id') and req.project_id else {}
        
        # Only inject the mapping prompt for entity_refs mode
        prompt_text = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.ref_image_url,
            req.last_frame_url,
            req.keyframes,
            req.ref_video_urls,
            entity_lookup=entity_lookup if is_reference_image_mode else None,
        )"""

t2 = text.replace(old_block, new_block)
if text == t2:
    print("Block not found!")
else:
    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(t2)
    print("Patched correctly!")