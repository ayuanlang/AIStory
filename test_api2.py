import sys; sys.path.append('backend')
from app.db.session import SessionLocal
from app.models.all_models import FunctionAPIConfig
db = SessionLocal()
conf = db.query(FunctionAPIConfig).filter_by(function_name='generate_subjects_i2i').first()
print(conf.api_settings if conf else 'None')
