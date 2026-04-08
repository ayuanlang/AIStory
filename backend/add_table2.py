import os
with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'DeletedMedia' not in text:
    text = text.replace('OSSProviderPool = getattr(models, "OSSProviderPool", None)', 'OSSProviderPool = getattr(models, "OSSProviderPool", None)\nDeletedMedia = getattr(models, "DeletedMedia", None)')
    
    table_create = '''
        if DeletedMedia is not None and not inspector.has_table("deleted_media"):
            DeletedMedia.__table__.create(bind=engine, checkfirst=True)
            logger.info("Created deleted_media table")
'''
    text = text.replace('if OSSProviderPool is not None and not inspector.has_table("oss_provider_pools"):', table_create.strip() + '\n        if OSSProviderPool is not None and not inspector.has_table("oss_provider_pools"):')
    
    with open('app/db/init_db.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated init_db.py')
else:
    print('DeletedMedia already in init_db.py')
