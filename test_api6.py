import sys; sys.path.append('backend')
from app.db.session import SessionLocal
from app.models.all_models import APIRoutingConfig
db = SessionLocal()
conf = db.query(APIRoutingConfig).first()
print(conf.use_function_based_routing if conf else 'None')
