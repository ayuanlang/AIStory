import os

with open('c:/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_func = '''import threading

def _cleanup_media_files(urls: List[str]):
    if not urls:
        return
        
    def _do_cleanup():
        import urllib.parse
        import logging
        try:
            from app.services.oss_storage_service import oss_storage_service
            from app.core.config import settings
            upload_root = settings.UPLOAD_DIR
            if not os.path.isabs(upload_root):
                upload_root = os.path.abspath(upload_root)

            def _to_upload_path(url_or_path: str) -> str:
                if not url_or_path:
                    return None
                raw = str(url_or_path).strip()
                if not raw:
                    return None
                try:
                    parsed = urllib.parse.urlparse(raw)
                    path_part = parsed.path if parsed.scheme else raw
                except Exception:
                    path_part = raw
                path_part = urllib.parse.unquote(path_part)
                path_part = path_part.lstrip("/")
                if path_part.startswith("uploads/"):
                    rel = path_part.replace("uploads/", "", 1)
                elif "/uploads/" in path_part:
                    rel = path_part.split("/uploads/", 1)[1]
                else:
                    rel = path_part
                abs_path = os.path.abspath(os.path.join(upload_root, rel))
                if not abs_path.startswith(upload_root):
                    return None
                return abs_path

            for u in set(urls):
                if not u: continue
                raw_url = str(u).strip()
                if not raw_url: continue
                if oss_storage_service.is_managed_url(raw_url):
                    try:
                        oss_storage_service.delete_url(raw_url)
                    except Exception as fe:
                        logging.warning(f"[_cleanup_media_files] Failed to delete OSS file {raw_url}: {fe}")
                else:
                    p = _to_upload_path(raw_url)
                    if p and os.path.exists(p) and os.path.isfile(p):
                        try:
                            os.remove(p)
                        except Exception as fe:
                            logging.warning(f"[_cleanup_media_files] Failed to delete local file {p}: {fe}")
        except Exception as e:
            logging.warning(f"[_cleanup_media_files] File cleanup failed: {e}")
            
    threading.Thread(target=_do_cleanup, daemon=True).start()'''

new_func = '''import threading

def _cleanup_media_files(urls: List[str]):
    if not urls:
        return
        
    def _do_record_cleanup():
        import logging
        from app.models.all_models import DeletedMedia
        from app.db.session import SessionLocal
        try:
            with SessionLocal() as db:
                for u in set(urls):
                    if not u: continue
                    raw_url = str(u).strip()
                    if not raw_url: continue
                    
                    record = DeletedMedia(url=raw_url)
                    db.add(record)
                db.commit()
        except Exception as e:
            logging.warning(f"[_cleanup_media_files] Failed to record deletion marks: {e}")
            
    threading.Thread(target=_do_record_cleanup, daemon=True).start()'''

text = text.replace(old_func, new_func)

with open('c:/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
