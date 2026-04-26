import os
import glob
import time

history_dir = os.path.expandvars(r'%APPDATA%\Code\User\History')
print(f'Scanning {history_dir}')

candidates = []
for root, dirs, files in os.walk(history_dir):
    for f in files:
        if len(f) > 0:
            candidates.append(os.path.join(root, f))

candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)

found = 0
for path in candidates[:500]:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            content = fh.read()
            if 'def _maybe_moderate_zlhub_images' in content and 'task_id' in content and '202' in content:
                print('Found potential match in', path)
                found += 1
                if found == 1:
                    with open('c:/AS/AIStory/backend/recovered_media_service.py', 'w', encoding='utf-8') as out:
                        out.write(content)
                        print("Wrote best match to c:/AS/AIStory/backend/recovered_media_service.py")
    except Exception:
        pass
