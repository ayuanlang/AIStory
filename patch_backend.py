import re

with open("backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace block 1: The Phase logic
pat1 = re.compile(
    r"(\s*)# 1\. First Call\s*\n\s*if skip_step1:.*?(?=\s*# Expose all merged loop variables)", 
    re.DOTALL
)

new_block1 = r"""\1# 1. Phase Execution Logic
\1is_entity_design_phase = (effective_scene_analysis_mode == "entity_design")
\1if is_entity_design_phase:
\1    if not cached_result_1:
\1        logger.error("Missing cached_result_1 for Entity Design phase")
\1    
\1    loop1_res = {
\1        "result_content": cached_result_1,
\1        "segments_meta": [],
\1        "usage_total": {},
\1        "resolved_llm_routing": {},
\1        "finish_reason": "stop",
\1        "continuation_stopped_by_max_segments": False,
\1        "output_char_cap_reached": False,
\1        "continuation_reason_counts": {},
\1        "continuation_by_structure": 0,
\1        "provider_limit_hints": [],
\1        "llm_fallback_warnings": []
\1    }
\1    result_content_1 = cached_result_1
\1
\1    # 2. Parse Subject Index
\1    import re
\1    subject_index_match = re.search(r"###\s*Subject\s*Index\n(.*?)(?=\n###|\Z)", result_content_1, flags=re.DOTALL | re.IGNORECASE)
\1    parsed_subject_index = subject_index_match.group(1).strip() if subject_index_match else ""
\1
\1    # 3. Create target_messages_2
\1    try:
\1        entity_design_skill = _resolve_prompt_text("skill:scene_analysis_feature_stack/entity_design.md")
\1    except Exception as e:
\1        logger.warning(f"Failed to load entity_design prompt, using default: {e}")
\1        entity_design_skill = "Provide detailed Entity Designs based on the subject index."
\1
\1    target_messages_2 = list(messages)
\1    target_messages_2.append({"role": "assistant", "content": result_content_1})
\1    target_messages_2.append({"role": "user", "content": f"Proceed to Phase 2 Entity Design.\n\nExtracted Subject Index:\n{parsed_subject_index}\n\nStrictly follow these guidelines:\n{entity_design_skill}"})
\1    loop2_res = await _run_loop(target_messages_2)
\1    result_content_2 = loop2_res["result_content"]
\1
\1    result_content = result_content_2
\1else:
\1    loop1_res = await _run_loop(messages)
\1    result_content_1 = loop1_res["result_content"]
\1    if script_hash:
\1        result_content_1 = f"<!-- script_hash: {script_hash} -->\n" + result_content_1
\1
\1    loop2_res = {
\1        "result_content": "",
\1        "segments_meta": [],
\1        "usage_total": {},
\1        "resolved_llm_routing": {},
\1        "finish_reason": loop1_res.get("finish_reason", "stop"),        
\1        "continuation_stopped_by_max_segments": False,
\1        "output_char_cap_reached": False,
\1        "continuation_reason_counts": {},
\1        "continuation_by_structure": 0,
\1        "provider_limit_hints": [],
\1        "llm_fallback_warnings": []
\1    }
\1    result_content_2 = ""
\1    result_content = result_content_1
"""
content = pat1.sub(new_block1, content)

# Replace block 2: The DB save logic
pat2 = re.compile(
    r"(\s*)episode\.ai_scene_analysis_result = result_content\s*\n\s*saved_to_episode = True\s*\n\s*debug_meta\[\"saved_to_episode\"\] = True\s*\n\s*debug_meta\[\"saved_episode_id\"\] = episode_id\s*\n\s*try:\s*\n\s*db\.flush\(\)\s*\n\s*except Exception:\s*\n\s*db\.rollback\(\)\s*\n\s*raise\s*\n\s*logger\.info\(\s*\n\s*\"\[analyze_scene\] Saved ai_scene_analysis_result to episode_id=%s chars=%s\",\s*\n\s*episode_id,\s*\n\s*len\(result_content or \"\"\),\s*\n\s*\)"
)

new_block2 = r"""\1if effective_scene_analysis_mode == "entity_design":
\1    episode.ai_entity_design_result = result_content
\1    logger.info("[analyze_scene] Saved ai_entity_design_result to episode_id=%s chars=%s", episode_id, len(result_content or ""))
\1else:
\1    episode.ai_scene_analysis_result = result_content
\1    logger.info("[analyze_scene] Saved ai_scene_analysis_result to episode_id=%s chars=%s", episode_id, len(result_content or ""))
\1saved_to_episode = True
\1debug_meta["saved_to_episode"] = True
\1debug_meta["saved_episode_id"] = episode_id
\1try:
\1    db.flush()
\1except Exception:
\1    db.rollback()
\1    raise"""
content = pat2.sub(new_block2, content)

with open("backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(content)
