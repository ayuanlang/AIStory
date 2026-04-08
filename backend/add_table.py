import os
with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'DeletedMedia' not in text:
    text = text.replace('SystemLog = getattr(models, "SystemLog", None)', 'SystemLog = getattr(models, "SystemLog", None)\nDeletedMedia = getattr(models, "DeletedMedia", None)')
    
    table_create = '''        if DeletedMedia is not None and not inspector.has_table("deleted_media"):
            DeletedMedia.__table__.create(bind=engine, checkfirst=True)
            logger.info("Created deleted_media table")'''
    
    text = text.replace('if SystemLog is not None and not inspector.has_table("system_logs"):', table_create + '\n        if SystemLog is not None and not inspector.has_table("system_logs"):')
    
    with open('app/db/init_db.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated init_db.py')
else:
    print('DeletedMedia already in init_db.py')
