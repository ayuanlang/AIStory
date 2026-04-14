import re

with open("backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

new_block = """
        _release_db_connection(db, "analyze_scene_llm_call")

        loop_res = await _run_loop(messages)
        result_content = loop_res["result_content"]

        # Expose all merged loop variables so the rest of the endpoint works seamlessly
        segments_meta = loop_res["segments_meta"]
        usage_total = loop_res["usage_total"]
        resolved_llm_routing = loop_res["resolved_llm_routing"]
        finish_reason = loop_res["finish_reason"]
        continuation_stopped_by_max_segments = loop_res["continuation_stopped_by_max_segments"]
        output_char_cap_reached = loop_res["output_char_cap_reached"]
        continuation_reason_counts = loop_res["continuation_reason_counts"]
        continuation_by_structure = loop_res["continuation_by_structure"]
        provider_limit_hints = loop_res["provider_limit_hints"]
        llm_fallback_warnings = loop_res["llm_fallback_warnings"]
"""

pattern = r"# Check cache.*?llm_fallback_warnings\s*=\s*list\(set\(loop1_res\[\"llm_fallback_warnings\"\] \+ loop2_res\[\"llm_fallback_warnings\"\]\)\)"

replaced = re.sub(pattern, new_block.strip("\n"), text, flags=re.DOTALL)

with open("backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(replaced)

print("Endpoints patched!")
