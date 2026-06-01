import os
import re

path = 'C:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'def _collect_subject_keys_by_bucket\(payload: Dict\[str, Any\]\) -> Dict\[str, Dict\[str, str\]\]:\s+collected: Dict\[str, Dict\[str, str\]\] = \{\s+"characters": \{\},\s+"props": \{\},\s+"environments": \{\},\s+"covers": \{\},\s+\}'

new_str = '''def _collect_subject_keys_by_bucket(payload: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
            collected: Dict[str, Dict[str, str]] = {
                "characters": {},
                "props": {},
                "environments": {},
                "covers": {},
                "posters": {},
            }'''

match = re.search(pattern, content)
if match:
    content = content[:match.start()] + new_str + content[match.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully replaced _collect_subject_keys_by_bucket initialization!")
else:
    print("Regex not matched!")
