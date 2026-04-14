
import sys, re

fname = "c:/AS/AIStory/backend/app/api/endpoints.py"
with open(fname, "r", encoding="utf-8") as f:
    text = f.read()

# For analyze_scene
pat_1 = r"(\s*# Resolve LLM config from user.s active setting.*?)\n(\s*config = agent_service.get_active_llm_config\()"
rep_1 = r"\1\n\2".replace(
    "\n",
    "\n        try:\n            db.commit()\n        except Exception:\n            pass\n"
)
text = re.sub(pat_1, r"\1\n        try:\n            db.commit()\n        except Exception:\n            pass\n\2", text, count=1)

# For ai_generate_shots and ai_regenerate_shots (both have identical lines)
old_line = "llm_config = agent_service.get_active_llm_config(current_user_id, system_api_id=system_api_id, function_name=function_name)"
new_line = "try:\n            db.commit()\n        except Exception:\n            pass\n        " + old_line
text = text.replace(old_line, new_line)

with open(fname, "w", encoding="utf-8") as f:
    f.write(text)
print("Endpoints patched")

