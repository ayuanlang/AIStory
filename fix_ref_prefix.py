import re

with open("c:/AS/AIStory/backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
"""        prompt_text = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.ref_image_url,
            req.last_frame_url,
            req.keyframes,
            req.ref_video_urls,
            entity_lookup=entity_lookup if is_reference_image_mode else None,
        )""",
"""        prompt_text = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.ref_image_url,
            req.last_frame_url,
            req.keyframes,
            req.ref_video_urls,
            entity_lookup=entity_lookup if is_reference_image_mode else None,
            inject_ref_prefix=getattr(req, "inject_ref_prefix", False),
        )"""
)

content = content.replace(
"""            req_payload["prompt"] = _append_video_api_ref_mapping(
                submit_prompt,
                submit_refs,
                submit_ref_image_url,
                submit_last_frame_url,
                submit_keyframes,
                submit_ref_video_urls,
                entity_lookup=submit_entity_lookup,
            )""",
"""            req_payload["prompt"] = _append_video_api_ref_mapping(
                submit_prompt,
                submit_refs,
                submit_ref_image_url,
                submit_last_frame_url,
                submit_keyframes,
                submit_ref_video_urls,
                entity_lookup=submit_entity_lookup,
                inject_ref_prefix=req_payload.get("inject_ref_prefix", False),
            )"""
)

content = content.replace(
"""        video_prompt = _append_video_api_ref_mapping(
            video_prompt_raw,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            None,
            entity_lookup=entity_lookup,
        )""",
"""        video_prompt = _append_video_api_ref_mapping(
            video_prompt_raw,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            None,
            entity_lookup=entity_lookup,
            inject_ref_prefix=getattr(req, "inject_ref_prefix", False) if hasattr(req, "inject_ref_prefix") else False,
        )"""
)

content = content.replace(
"""            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
                None,
                entity_lookup=entity_lookup,
            )""",
"""            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
                None,
                entity_lookup=entity_lookup,
                inject_ref_prefix=getattr(req, "inject_ref_prefix", False) if hasattr(req, "inject_ref_prefix") else False,
            )"""
)

with open("c:/AS/AIStory/backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(content)

print("done")