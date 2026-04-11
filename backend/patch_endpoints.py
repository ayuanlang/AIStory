import sys

with open('app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = '''        # Copy known fields
        for field in ["shot_number", "shot_id", "project_id", "episode_id", "asset_type", "entity_id", "entity_name", "subject_name", "subject_type", "entity_type", "source_asset_url", "idempotency_key"]:
            val = get_attr(req, field)
            if val: meta[field] = val'''

new_block = '''        # Copy known fields
        for field in ["shot_number", "shot_id", "project_id", "episode_id", "asset_type", "entity_id", "entity_name", "subject_name", "subject_type", "entity_type", "source_asset_url", "idempotency_key"]:
            val = get_attr(req, field)
            if val: meta[field] = val

        # Map reference URLs to source_asset_url for asset dependency tracking
        if not meta.get("source_asset_url"):
            for ref_field in ["ref_image_url", "ref_video_urls", "last_frame_url", "base_image", "seed_image"]:
                ref_val = get_attr(req, ref_field)
                if ref_val:
                    actual_url = ref_val[0] if isinstance(ref_val, list) and len(ref_val) > 0 else ref_val
                    if isinstance(actual_url, str) and actual_url.startswith("http"):
                        meta["source_asset_url"] = actual_url
                        break'''

if old_block in text:
    text = text.replace(old_block, new_block, 1)
    with open('app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched endpoints.py!")
else:
    print("Could not find the target block.")

