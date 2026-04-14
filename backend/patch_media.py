
with open("c:/AS/AIStory/backend/app/services/media_service.py", "r", encoding="utf-8") as f:
    text = f.read()

old_code = """                    try:
                        from app.services.system_log_service import log_action"""

new_code = """                    try:
                        session.commit()
                    except Exception:
                        pass
                    try:
                        from app.services.system_log_service import log_action"""

if old_code in text:
    text = text.replace(old_code, new_code)
    print("Patched media_service")
with open("c:/AS/AIStory/backend/app/services/media_service.py", "w", encoding="utf-8") as f:
    f.write(text)

