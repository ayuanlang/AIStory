import sys; sys.path.append('backend')
import asyncio
from app.db.session import SessionLocal
from app.api.endpoints import _resolve_media_runtime_target
from app.models.all_models import User
db=SessionLocal()
target = _resolve_media_runtime_target(provider=None, model=None, media_type='image', category='Image', user_id=3, user_credits=1000, function_name='generate_subjects_t2i', system_api_id=490)
print(target.get('pre_api_cfg', {}).get('config', {}).get('__resolved_source'))
