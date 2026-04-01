import os
from app.services.oss_storage_service import oss_storage_service
from app.db.session import SessionLocal

def run_test():
    # Make a dummy file
    with open('dummy.png', 'wb') as f:
        f.write(b'dummy image content')
        
    db = SessionLocal()
    print('is_enabled:', oss_storage_service.is_enabled(db))
    
    try:
        oss_res = oss_storage_service.upload_file(
            'dummy.png',
            user_id=3,
            filename='dummy.png',
            content_type='image/png',
            category='uploads'
        )
        print('oss_res:', oss_res)
    except Exception as e:
        print('Exception:', e)
        
if __name__ == '__main__':
    run_test()
