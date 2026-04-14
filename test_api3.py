import sys; sys.path.append('backend')
from app.db.session import SessionLocal
from app.services.media_service import media_service
db = SessionLocal()
res = media_service.get_api_config(provider=None, user_id=3, category='Image', requested_model=None, strict_provider=False, function_name='generate_subjects_t2i', system_api_id=490)
print(res and res.get('config', {}).get('__resolved_source'))
