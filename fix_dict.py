import re

with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. line 4943: _extract_expected_subjects_from_subject_index
text = text.replace('''        def _extract_expected_subjects_from_subject_index(text: str) -> Dict[str, Any]:
            expected: Dict[str, Dict[str, str]] = {
                "characters": {},
                "props": {},
                "environments": {},
                "covers": {},
            }''', '''        def _extract_expected_subjects_from_subject_index(text: str) -> Dict[str, Any]:
            expected: Dict[str, Dict[str, str]] = {
                "characters": {},
                "props": {},
                "environments": {},
                "covers": {},
                "posters": {},
            }''')

# 2. line 5105: reconciled
text = text.replace('''            reconciled: Dict[str, List[Dict[str, Any]]] = {
                "characters": [],
                "props": [],
                "environments": [],
                "covers": [],
            }''', '''            reconciled: Dict[str, List[Dict[str, Any]]] = {
                "characters": [],
                "props": [],
                "environments": [],
                "covers": [],
                "posters": [],
            }''')

# 3. line 5262: expected_by_bucket
text = text.replace('''                    "expected_by_bucket": {
                        "characters": 0,
                        "props": 0,
                        "environments": 0,
                        "covers": 0,
                    },''', '''                    "expected_by_bucket": {
                        "characters": 0,
                        "props": 0,
                        "environments": 0,
                        "covers": 0,
                        "posters": 0,
                    },''')

# 4. line 5412 & 5418: selected_counts & aggregated_counts
text = text.replace('''            return {
                "selected_counts": {
                    "characters": len(selected_keys.get("characters") or {}),
                    "props": len(selected_keys.get("props") or {}),
                    "environments": len(selected_keys.get("environments") or {}),
                    "covers": len(selected_keys.get("covers") or {}),
                },
                "aggregated_counts": {
                    "characters": len(aggregated_keys.get("characters") or {}),
                    "props": len(aggregated_keys.get("props") or {}),
                    "environments": len(aggregated_keys.get("environments") or {}),
                    "covers": len(aggregated_keys.get("covers") or {}),
                },''', '''            return {
                "selected_counts": {
                    "characters": len(selected_keys.get("characters") or {}),
                    "props": len(selected_keys.get("props") or {}),
                    "environments": len(selected_keys.get("environments") or {}),
                    "covers": len(selected_keys.get("covers") or {}),
                    "posters": len(selected_keys.get("posters") or {}),
                },
                "aggregated_counts": {
                    "characters": len(aggregated_keys.get("characters") or {}),
                    "props": len(aggregated_keys.get("props") or {}),
                    "environments": len(aggregated_keys.get("environments") or {}),
                    "covers": len(aggregated_keys.get("covers") or {}),
                    "posters": len(aggregated_keys.get("posters") or {}),
                },''')

# 5. line 13860: inventory
text = text.replace('''    inventory: Dict[str, List[Dict[str, str]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
    }''', '''    inventory: Dict[str, List[Dict[str, str]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
        "posters": [],
    }''')

# 6. line 13919: type_names
text = text.replace('''    type_names = {
        "characters": "角色",
        "props": "道具",
        "environments": "场景",
        "covers": "封面"
    }''', '''    type_names = {
        "characters": "角色",
        "props": "道具",
        "environments": "场景",
        "covers": "封面",
        "posters": "海报"
    }''')

with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patch applied")
