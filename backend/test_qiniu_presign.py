import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from app.db.session import SessionLocal
from app.services.oss_storage_service import oss_storage_service

db = SessionLocal()
pool = oss_storage_service._pick_pool(db)
print("Pool provider:", pool.provider)
print("Pool endpoint:", pool.endpoint)
print("Pool bucket:", pool.bucket)
print("Pool public_base_url:", getattr(pool, 'public_base_url', None))

cred, _ = oss_storage_service._pick_credential(pool)
client = oss_storage_service._build_client(pool, cred)
url = client.generate_presigned_url(
    'get_object',
    Params={'Bucket': pool.bucket, 'Key': 'aistory/upload/3/assets/928861ec-3d58-4d21-a695-c3036ea06b01.png'},
    ExpiresIn=3600
)
print("Presigned URL:", url)
