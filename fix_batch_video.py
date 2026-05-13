import sys

def process():
    file_path = "c:/AS/AIStory/backend/app/api/endpoints.py"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Define the first replacement (video_prompt)
    old_code_1 = """        ordered_video_refs = [x for x in dict.fromkeys(ordered_video_refs) if x]

        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            entity_lookup=entity_lookup,
        )

        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()"""

    new_code_1 = """        ordered_video_refs = [x for x in dict.fromkeys(ordered_video_refs) if x]

        system_api_id_val = system_api_id
        if not system_api_id_val and getattr(episode, "system_api_id", None):
            system_api_id_val = episode.system_api_id
            
        is_seedance_batch = False
        if system_api_id_val:
            pre_api_cfg = _fetch_system_api_config(item_db, system_api_id_val, "video")
            if "seedance" in str(pre_api_cfg.get("provider") or "").lower() or "seedance" in str(pre_api_cfg.get("model") or "").lower():
                is_seedance_batch = True

        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            provider="seedance" if is_seedance_batch else None,
            entity_lookup=entity_lookup,
        )

        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()"""

    content = content.replace(old_code_1, new_code_1)

    # Define the second replacement (video_prompt_cn)
    old_code_2 = """            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
                entity_lookup=entity_lookup,
            )"""

    new_code_2 = """            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
                provider="seedance" if is_seedance_batch else None,
                entity_lookup=entity_lookup,
            )"""
            
    content = content.replace(old_code_2, new_code_2)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Replaced!")

process()
