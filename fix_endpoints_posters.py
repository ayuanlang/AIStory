import os
import re

path = 'C:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'def _extract_entities_from_json_candidates\(text: str\) -> Dict\[str, List\[Dict\[str, Any\]\]\]:\s+payload: Dict\[str, List\[Dict\[str, Any\]\]\] = \{\s+"characters": \[\], "covers": \[\],\s+"props": \[\],\s+"environments": \[\],\s+\}'

new_str = '''def _extract_entities_from_json_candidates(text: str) -> Dict[str, List[Dict[str, Any]]]:
            payload: Dict[str, List[Dict[str, Any]]] = {
                "characters": [], "covers": [],
                "props": [],
                "environments": [],
                "posters": [],
            }'''

match = re.search(pattern, content)
if match:
    content = content[:match.start()] + new_str + content[match.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully replaced _extract_entities_from_json_candidates initialization!")
else:
    print("Regex not matched!")
