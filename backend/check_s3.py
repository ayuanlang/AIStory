from app.services.oss_storage_service import oss_storage_service
from app.db.session import SessionLocal

def test_b2():
    db = SessionLocal()
    try:
        pools = oss_storage_service._get_active_pools(db)
        b2_pool = next((p for p in pools if p.provider == 'backblaze'), None)
        if not b2_pool:
            print('No B2 pool found')
            return
            
        cred, _ = oss_storage_service._pick_credential(b2_pool)
        client = oss_storage_service._build_client(b2_pool, cred)
        
        print(f'Uploading to {b2_pool.bucket} via {b2_pool.endpoint} using region {client.meta.region_name}...')
        try:
            res = client.put_object(Bucket=b2_pool.bucket, Key='test_diag.txt', Body=b'test')
            print('Success!')
        except Exception as e:
            print(f'Error: {e}')
            
    finally:
        db.close()

if __name__ == '__main__':
    test_b2()
