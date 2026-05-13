import re

with open("c:/AS/AIStory/backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
"""                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                            entity_lookup=entity_lookup,
                        )""",
"""                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                            entity_lookup=entity_lookup,
                            inject_ref_prefix=getattr(req, "inject_ref_prefix", False) if hasattr(req, "inject_ref_prefix") else False,
                        )"""
)

content = content.replace(
"""                            video_prompt_cn = _append_video_api_ref_mapping(
                                video_prompt_cn,
                                ordered_video_refs,
                                normalized_refs,
                                normalized_last_frame_url,
                                None,
                                entity_lookup=entity_lookup,
                            )""",
"""                            video_prompt_cn = _append_video_api_ref_mapping(
                                video_prompt_cn,
                                ordered_video_refs,
                                normalized_refs,
                                normalized_last_frame_url,
                                None,
                                entity_lookup=entity_lookup,
                                inject_ref_prefix=getattr(req, "inject_ref_prefix", False) if hasattr(req, "inject_ref_prefix") else False,
                            )"""
)

with open("c:/AS/AIStory/backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(content)

print("done")