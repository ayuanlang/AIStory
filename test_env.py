import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from backend.app.db.session import SessionLocal
from backend.app.models.all_models import FunctionAPIConfig

db = SessionLocal()
conf = db.query(FunctionAPIConfig).filter_by(function_name='generate_subjects_t2i').first()
if conf:
    print(conf.api_settings)
else:
    print('None')
