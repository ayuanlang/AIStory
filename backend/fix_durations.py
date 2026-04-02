import codecs
import re

p = r'C:\AIStory\backend\app\services\media_service.py'
with codecs.open(p, 'r', 'utf-8') as f:
    text = f.read()

text = re.sub(
    r'(duration_values_raw = getattr\(row, "durations_seconds", None\)\s*)(duration_values_text = self\._normalize_str_list\(duration_values_raw\))',
    r'\1if not duration_values_raw:\n                duration_values_raw = enum_catalog.get("duration") if isinstance(enum_catalog, dict) else None\n            \2',
    text
)

with codecs.open(p, 'w', 'utf-8') as f:
    f.write(text)