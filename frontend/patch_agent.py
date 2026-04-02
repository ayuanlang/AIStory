import re

with open('C:/AIStory/backend/app/services/agent_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_def = '    def get_active_llm_config(self, user_id: int = 1, category: str = "LLM") -> Dict[str, Any]:'
new_def = '    def get_active_llm_config(self, user_id: int = 1, category: str = "LLM", system_api_id: Optional[int] = None, function_name: Optional[str] = None) -> Dict[str, Any]:'

text = text.replace(old_def, new_def)

old_call = '''            unified = _media_service.get_api_config(
                provider=None,
                user_id=user_id,
                category=resolved_category,
                requested_model=None,
                user_credits=0,
                strict_provider=False,
            ) or {}'''

new_call = '''            unified = _media_service.get_api_config(
                provider=None,
                user_id=user_id,
                category=resolved_category,
                requested_model=None,
                user_credits=0,
                strict_provider=False,
                system_api_id=system_api_id,
                function_name=function_name,
            ) or {}'''

text = text.replace(old_call, new_call)

with open('C:/AIStory/backend/app/services/agent_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("agent_service.py patched")
