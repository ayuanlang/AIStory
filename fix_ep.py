import sys
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

ep = '''
from app.schemas.system_log import LLMCallLogOut

@router.get("/admin/llm_logs", response_model=List[LLMCallLogOut])
def get_llm_call_logs(
    limit: int = 100,
    offset: int = 0,
    provider: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    from app.models.all_models import LLMCallLog
    query = db.query(LLMCallLog)
    if provider:
        query = query.filter(LLMCallLog.provider == provider)
    if tag:
        query = query.filter(LLMCallLog.tag == tag)
    logs = query.order_by(LLMCallLog.id.desc()).offset(offset).limit(limit).all()
    return logs
'''

if 'def get_llm_call_logs' not in text:
    target = '@router.get("/admin/runtime-logs/files"'
    idx = text.find(target)
    if idx != -1:
        text = text[:idx] + ep + '\n' + text[idx:]
        with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Injected via fix_ep.py")
