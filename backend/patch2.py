
import sys

with open("c:/AS/AIStory/backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

old_1 = """        config = agent_service.get_active_llm_config(
            user_id=current_user_id,
            category="LLM","""

new_1 = """        try:
            db.commit()
        except Exception:
            pass
        config = agent_service.get_active_llm_config(
            user_id=current_user_id,
            category="LLM","""

old_2 = "        llm_config = agent_service.get_active_llm_config(current_user_id, system_api_id=system_api_id, function_name=function_name)"
new_2 = """        try:
            db.commit()
        except Exception:
            pass
        llm_config = agent_service.get_active_llm_config(current_user_id, system_api_id=system_api_id, function_name=function_name)"""

if old_1 in text:
    text = text.replace(old_1, new_1)
    print("Patched analyze_scene")

if old_2 in text:
    text = text.replace(old_2, new_2)
    print("Patched ai_generate_shots")
    
# also patch ai_regenerate_shots just in case
old_3 = "        llm_config = agent_service.get_active_llm_config(current_user_id, system_api_id=system_api_id, function_name=function_name)"
if old_3 in text:
    # already handled by old_2 if identical
    pass

with open("c:/AS/AIStory/backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(text)

