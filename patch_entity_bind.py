with open("backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

target = "def _bind_generated_media_to_entity(db: Session, current_user: User, req: Any, media_url: Optional[str], oss_uploaded_success: Optional[bool] = None) -> None:\\n    if not media_url:\\n        return\\n\\n    def get_attr("
replacement = "def _bind_generated_media_to_entity(db: Session, current_user: User, req: Any, media_url: Optional[str], oss_uploaded_success: Optional[bool] = None) -> None:\\n    if not media_url:\\n        return\\n\\n    if media_url.startswith(\\\"/\\\") or any(domain in media_url.lower() for domain in [\\\"clouddn.com\\\", \\\"backblazeb2.com\\\", \\\"qiniucs.com\\\", \\\"qiniu.com\\\", \\\".bkt.\\\", \\\"aistory\\\"]):\\n        oss_uploaded_success = True\\n\\n    def get_attr("
    
import re
target2 = re.compile(r"def _bind_generated_media_to_entity.*?\n\s+if not media_url:\n\s+return\n\n\s+def get_attr")
if target2.search(text):
    text = target2.sub(replacement.replace("\\n", "\n").replace("\\\"", "\""), text)
    with open("backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("replaces ok via regex")
else:
    print("target not found")