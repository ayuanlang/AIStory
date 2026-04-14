import sys; sys.path.append('backend')
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting, APIRoutingConfig
from app.api.settings import get_task_default_system_setting
db = SessionLocal()
# check global config
cfg = db.query(APIRoutingConfig).first()
print(cfg.use_function_based_routing)
task_def = get_task_default_system_setting(db, 'Image')
print(f'Task default image api: {task_def.id if task_def else None}')
