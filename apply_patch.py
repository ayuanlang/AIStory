import re

with open('C:/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Change the base prompt to scene_planning.md
text = text.replace(
    'prompt_filename = request.prompt_file or "scene_analysis.txt"',
    'prompt_filename = request.prompt_file or "skill:scene_analysis_feature_stack/scene_planning.md"'
)

# 2. Extract the loop logic
pattern = re.compile(
    r'(        # Construct messages\n        messages = \[\n            \{"role": "system", "content": system_instruction\},\n            \{"role": "user", "content": user_content\}\n        \]\n)(        \n        # Resolve LLM config.*?)(        response_payload: Dict\[str, Any\] = \{"success": True, "result": result_content, "meta": debug_meta\})',
    re.DOTALL
)
match = pattern.search(text)

if match:
    pre = match.group(1)
    loop = match.group(2)
    post = match.group(3)
    
    # We will indent the loop by 4 spaces to put it in a function wrapper
    indented_loop = "\n".join("    " + line for line in loop.split("\n"))
    
    new_code = f'''{pre}
        async def _run_llm_loop(step_messages):
{indented_loop}
            return result_content, debug_meta, integrity_meta

        # Step 1: Execute scene planning
        result_content_1, debug_meta_1, integrity_meta_1 = await _run_llm_loop(messages)

        # Step 2: Extract Subject Index and run entity design
        subject_index_match = re.search(r"(?im)^\s*(?:#{{1,6}}\s*)?Subject\s*Index\b\s*([\\s\\S]*?)(?:^\s*(?:#{{1,6}}\s*)?Part\s*2\b.*)?\Z", result_content_1)
        subject_index = subject_index_match.group(1).strip() if subject_index_match else ""

        step2_sys = _resolve_prompt_text("skill:scene_analysis_feature_stack/entity_design.md")
        messages_step_2 = [
            {{"role": "system", "content": system_instruction}},
            {{"role": "user", "content": f"Extracted Subject Index:\\n{{subject_index}}\\n\\nNow follow Phase 2 Entity Design rules:\\n{{step2_sys}}\\n\\n{{user_content}}"}}
        ]
        
        result_content_2, debug_meta_2, integrity_meta_2 = await _run_llm_loop(messages_step_2)

        # Combine
        result_content = result_content_1 + "\\n\\n" + result_content_2
        debug_meta = debug_meta_1
        debug_meta.update(debug_meta_2) # Simplified merge
        integrity_meta = integrity_meta_1
        
        # We need to simulate these variables for the parsing block 
        # (originally computed at the end of the loop)
        config = agent_service.get_active_llm_config(user_id=current_user_id, category="LLM")
        finish_reason = "stop"
        output_char_cap_reached = False
        segments_meta = []
        llm_fallback_warnings = []
{post}'''
    
    text = text.replace(match.group(0), new_code)
    print("Patched LLM loop successfully.")
else:
    print("Could not find the LLM loop pattern.")

with open('C:/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
