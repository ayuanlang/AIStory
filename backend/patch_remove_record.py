import os
import re

with open('c:/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_func_pattern = r'import threading\n\ndef _cleanup_media_files\(urls: List\[str\]\):.*?\n\n'
new_func = '''def _cleanup_media_files(urls):
    # TODO: Refactor global deletion logic for media files.
    pass

'''

text = re.sub(old_func_pattern, new_func, text, flags=re.DOTALL)

with open('c:/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched successfully')
