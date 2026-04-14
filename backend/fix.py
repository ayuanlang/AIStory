
import re

fname = "C:/AS/AIStory/backend/app/api/endpoints.py"
with open(fname, "r", encoding="utf-8") as f:
    text = f.read()

# Add try: db.commit() in analyze_scene before agent_service.get_active_llm_config
text = text.replace(
    "config = agent_service.get_active_llm_config(\n            user_id=current_user_id,\n            category=\"LLM\",",
    "try:\n            db.commit()\n        except Exception:\n            pass\n        config = agent_service.get_active_llm_config(\n            user_id=current_user_id,\n            category=\"LLM\","
)

# And in ai_generate_shots:
text = text.replace(
    "llm_config = agent_service.get_active_llm_config(current_user_id, system_api_id=system_api_id, function_name=function_name)",
    "try:\n            db.commit()\n        except Exception:\n            pass\n        llm_config = agent_service.get_active_llm_config(current_user_id, system_api_id=system_api_id, function_name=function_name)"
)

# And in media_service.py get_api_config:
mname = "C:/AS/AIStory/backend/app/services/media_service.py"
with open(mname, "r", encoding="utf-8") as f:
    mtext = f.read()
mtext = mtext.replace(
    "try:\n                        from app.services.system_log_service import log_action",
    "try:\n                        session.commit()\n                    except Exception:\n                        pass\n                    try:\n                        from app.services.system_log_service import log_action"
)

with open(fname, "w", encoding="utf-8") as f:
    f.write(text)

with open(mname, "w", encoding="utf-8") as f:
    f.write(mtext)
print("patched")

