import os

with open('c:/AIStory/backend/app/db/init_db.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'if DeletedMedia is not None and not inspector.has_table("deleted_media"):' in line:
        new_lines.append('            if DeletedMedia is not None and not inspector.has_table("deleted_media"):\n')
    elif 'DeletedMedia.__table__.create(bind=engine, checkfirst=True)' in line:
        new_lines.append('                DeletedMedia.__table__.create(bind=engine, checkfirst=True)\n')
    elif 'logger.info("Created deleted_media table")' in line:
        new_lines.append('                logger.info("Created deleted_media table")\n')
    elif 'if OSSProviderPool is not None and not inspector.has_table("oss_provider_pools"):' in line:
        new_lines.append('            if OSSProviderPool is not None and not inspector.has_table("oss_provider_pools"):\n')
    else:
        new_lines.append(line)

with open('c:/AIStory/backend/app/db/init_db.py', 'w', encoding='utf-8') as f:
    f.write(''.join(new_lines))

print('Fixed indentation.')
