import re
import os

file_path = "backend/app/api/endpoints.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define the exact target block to replace
start_marker = "        result_parts: List[str] = []\n        segments_meta: List[Dict[str, Any]] = []"
end_marker = "        if finish_reason is not None and _is_length_finish_reason(finish_reason) and len(segments_meta) >= max_segments:\n            continuation_stopped_by_max_segments = True\n\n        result_content = \"\".join(result_parts)"

try:
    start_idx = content.index(start_marker)
    end_idx = content.index(end_marker) + len(end_marker)
except ValueError as e:
    print(f"Could not find the target block: {e}")
    exit(1)

original_block = content[start_idx:end_idx]

# Let's craft the new block

new_block = r"""\
        def _dedupe_overlap(existing: str, incoming: str) -> str:
            if not existing or not incoming:
                return incoming
            candidates = [
                existing[-200:],
                existing[-400:],
                existing[-800:],
            ]
            for c in candidates:
                if c and incoming.startswith(c):
                    return incoming[len(c):]
            inc_l = incoming.lstrip()
            for c in candidates:
                if c and inc_l.startswith(c):
                    return inc_l[len(c):]
            return incoming

        async def _run_loop(target_messages):
            result_parts_loop: List[str] = []
            segments_meta_loop: List[Dict[str, Any]] = []
            usage_total_loop: Dict[str, Any] = {}
            resolved_llm_routing_loop: Dict[str, Any] = {}
            finish_reason_loop = None
            continuation_stopped_by_max_segments_loop = False
            output_char_cap_reached_loop = False
            continuation_reason_counts_loop: Dict[str, int] = {}
            continuation_by_structure_loop = 0
            provider_limit_hints_loop: List[str] = []
            llm_fallback_warnings_loop: List[str] = []

            current_messages = list(target_messages)
            system_only_messages = []
            try:
                if target_messages and isinstance(target_messages[0], dict) and target_messages[0].get("role") == "system":
                    system_only_messages = [target_messages[0]]
            except Exception:
                system_only_messages = []

            for seg_idx in range(1, max_segments + 1):
                llm_resp = await _await_analyze_scene_segment(current_messages, config)
                current_routing = _extract_llm_routing_metadata(llm_resp)
                if current_routing:
                    resolved_llm_routing_loop = current_routing
                raw_part = llm_resp.get("raw_content")
                if not isinstance(raw_part, str):
                    raw_part = llm_resp.get("content", "") or ""
                part_usage = llm_resp.get("usage", {}) or {}
                part_finish = llm_resp.get("finish_reason")
                part_limit_hints = llm_resp.get("token_limit_hints", []) or []
                part_extraction_diag = llm_resp.get("extraction_diagnostics", {}) or {}
                part_fallback_warnings = llm_resp.get("fallback_warnings", []) or []
                if isinstance(part_limit_hints, list):
                    for hint in part_limit_hints:
                        hint_text = str(hint or "").strip()
                        if hint_text and hint_text not in provider_limit_hints_loop:
                            provider_limit_hints_loop.append(hint_text)
                if isinstance(part_fallback_warnings, list):
                    for warn in part_fallback_warnings:
                        warn_text = str(warn or "").strip()
                        if warn_text and warn_text not in llm_fallback_warnings_loop:
                            llm_fallback_warnings_loop.append(warn_text)

                usage_total_loop = _merge_usage(usage_total_loop, part_usage)
                finish_reason_loop = part_finish

                existing = "".join(result_parts_loop)
                part_content = _dedupe_overlap(existing, raw_part)
                result_parts_loop.append(part_content)
                segments_meta_loop.append({
                    "index": seg_idx,
                    "finish_reason": part_finish,
                    "output_chars": len(raw_part),
                    "output_tokens_est": _estimate_tokens(raw_part),
                    "deduped_chars": len(part_content),
                    "usage": part_usage,
                    "token_limit_hints": part_limit_hints,
                    "extraction_diagnostics": part_extraction_diag,
                })

                accumulated = "".join(result_parts_loop)
                if len(accumulated) >= _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP:
                    output_char_cap_reached_loop = True
                    finish_reason_loop = part_finish or finish_reason_loop or "safety_output_cap"
                    logger.warning(
                        "[analyze_scene] safety_output_cap_reached episode_id=%s provider=%s model=%s chars=%s cap=%s segments=%s",
                        getattr(request, "episode_id", None),
                        (config or {}).get("provider"),
                        (config or {}).get("model"),
                        len(accumulated),
                        _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP,
                        len(segments_meta_loop or []),
                    )
                    break
                section_meta = _detect_scene_output_sections(accumulated)
                missing_sections = [str(x) for x in (section_meta.get("missing_sections") or []) if str(x)]
                continue_due_to_length = _is_length_finish_reason(part_finish)
                continue_due_to_structure = (
                    not continue_due_to_length
                    and bool(missing_sections)
                    and seg_idx < max_segments
                    and continuation_by_structure_loop < 3
                    and bool(accumulated.strip())
                )

                # Stop if not truncated.
                if not continue_due_to_length and not continue_due_to_structure:
                    break

                # Stop if provider returned nothing new.
                if not raw_part.strip():
                    break

                # Ask for continuation; include only a short suffix of the accumulated output.
                suffix = accumulated[-tail_chars:] if len(accumulated) > tail_chars else accumulated
                continuation_reason = "length"
                if continue_due_to_structure:
                    continuation_by_structure_loop += 1
                    continuation_reason = "missing_required_sections"
                    continuation_instruction = continuation_instruction_incomplete_tpl.format(
                        missing_sections=", ".join(missing_sections),
                        suffix=suffix,
                    )
                else:
                    continuation_instruction = continuation_instruction_tpl.format(suffix=suffix)

                continuation_reason_counts_loop[continuation_reason] = int(continuation_reason_counts_loop.get(continuation_reason) or 0) + 1

                # Continuation does not require re-sending the whole script; keep only system + tail.
                base_for_continue = system_only_messages or list(target_messages)
                current_messages = list(base_for_continue) + [
                    {"role": "assistant", "content": suffix},
                    {"role": "user", "content": continuation_instruction},
                ]

            if finish_reason_loop is not None and _is_length_finish_reason(finish_reason_loop) and len(segments_meta_loop) >= max_segments:
                continuation_stopped_by_max_segments_loop = True

            return {
                "result_content": "".join(result_parts_loop),
                "segments_meta": segments_meta_loop,
                "usage_total": usage_total_loop,
                "resolved_llm_routing": resolved_llm_routing_loop,
                "finish_reason": finish_reason_loop,
                "continuation_stopped_by_max_segments": continuation_stopped_by_max_segments_loop,
                "output_char_cap_reached": output_char_cap_reached_loop,
                "continuation_reason_counts": continuation_reason_counts_loop,
                "continuation_by_structure": continuation_by_structure_loop,
                "provider_limit_hints": provider_limit_hints_loop,
                "llm_fallback_warnings": llm_fallback_warnings_loop,
            }

        _release_db_connection(db, "analyze_scene_llm_call")

        # 1. First Call
        loop1_res = await _run_loop(messages)
        result_content_1 = loop1_res["result_content"]
        
        # 2. Parse Subject Index
        import re
        subject_index_match = re.search(r"###\s*Subject\s*Index\n(.*?)(?=\n###|\Z)", result_content_1, flags=re.DOTALL | re.IGNORECASE)
        parsed_subject_index = subject_index_match.group(1).strip() if subject_index_match else ""
        
        # 3. Create target_messages_2
        try:
            from app.core.prompts.skills_loader import get_skill_prompt_text
            # Production path: common + typed prompts (not deprecated entity_design.md monolith)
            entity_design_skill = get_skill_prompt_text("scene_analysis_feature_stack/entity_design_common.md")
        except Exception as e:
            logger.warning(f"Failed to load entity_design_common prompt, using default: {e}")
            entity_design_skill = "Provide detailed Entity Designs based on the subject index. Follow entity_design_common.md + typed character/prop/environment_and_poster prompts."

        target_messages_2 = list(messages)
        target_messages_2.append({"role": "assistant", "content": result_content_1})
        target_messages_2.append({"role": "user", "content": f"Based on the following subject index, please provide the detailed Entity Designs using the required format:\n\n{parsed_subject_index}\n\nStrictly follow these guidelines (common baseline; production uses common + typed prompts):\n{entity_design_skill}"})
        
        # 4. Call again
        loop2_res = await _run_loop(target_messages_2)
        result_content_2 = loop2_res["result_content"]
        
        # 5. Combine results
        result_content = result_content_1 + "\n\n" + result_content_2

        # Expose all merged loop variables so the rest of the endpoint works seamlessly
        segments_meta = loop1_res["segments_meta"] + loop2_res["segments_meta"]
        usage_total = _merge_usage(loop1_res["usage_total"], loop2_res["usage_total"])
        resolved_llm_routing = loop2_res["resolved_llm_routing"] or loop1_res["resolved_llm_routing"]
        finish_reason = loop2_res["finish_reason"]
        continuation_stopped_by_max_segments = loop1_res["continuation_stopped_by_max_segments"] or loop2_res["continuation_stopped_by_max_segments"]
        output_char_cap_reached = loop1_res["output_char_cap_reached"] or loop2_res["output_char_cap_reached"]
        continuation_reason_counts = dict(loop1_res["continuation_reason_counts"])
        for k, v in loop2_res["continuation_reason_counts"].items():
            continuation_reason_counts[k] = continuation_reason_counts.get(k, 0) + v
        continuation_by_structure = loop1_res["continuation_by_structure"] + loop2_res["continuation_by_structure"]
        provider_limit_hints = list(set(loop1_res["provider_limit_hints"] + loop2_res["provider_limit_hints"]))
        llm_fallback_warnings = list(set(loop1_res["llm_fallback_warnings"] + loop2_res["llm_fallback_warnings"]))"""

new_content = content[:start_idx] + new_block + content[end_idx:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Rewritten successfully.")
