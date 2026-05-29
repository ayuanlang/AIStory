import os
import time

history_dir = os.path.expandvars(r'%APPDATA%\Code\User\History')
now = time.time()
found = []
for root, dirs, files in os.walk(history_dir):
    for f in files:
        if f == 'entries.json': continue
        path = os.path.join(root, f)
        if os.path.getsize(path) > 300000:
            mtime = os.path.getmtime(path)
            # if within last 24 hours
            if now - mtime < 186400:
                found.append((mtime, path))

found.sort(key=lambda x: x[0], reverse=True)
for mtime, path in found[:10]:
    print(path, time.ctime(mtime))
