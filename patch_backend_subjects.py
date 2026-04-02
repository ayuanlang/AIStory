import re

with open('c:/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '''class CharacterProfileGenerateRequest(BaseModel):
    name: str''',
    '''class CharacterProfileGenerateRequest(BaseModel):
    name: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None'''
)

text = text.replace(
    'llm_config = agent_service.get_active_llm_config(current_user.id)',
    'llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))'
)

with open('c:/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)

