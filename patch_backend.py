import re

with open("backend/app/api/settings.py", "r", encoding="utf-8") as f:
    content = f.read()

old_append = '''                valid_settings.append({
                    "system_api_id": sys_api.id,
                    "system_api_name": sys_api.name,
                    "system_api_model": sys_api.model or "",
                    "priority": item.get("priority", 0),
                    "is_fallback": item.get("is_fallback", False)
                })'''

new_append = '''                valid_settings.append({
                    "system_api_id": sys_api.id,
                    "system_api_name": sys_api.name,
                    "system_api_model": sys_api.model or "",
                    "priority": item.get("priority", 0),
                    "is_fallback": item.get("is_fallback", False),
                    "alias": item.get("alias", sys_api.model or sys_api.name or f"API {sys_api.id}"),
                    "applicable_languages": item.get("applicable_languages", []),
                    "explicit_selection": item.get("explicit_selection", False),
                    "strict_provider": item.get("strict_provider", False)
                })'''

content = content.replace(old_append, new_append)

with open("backend/app/api/settings.py", "w", encoding="utf-8") as f:
    f.write(content)
