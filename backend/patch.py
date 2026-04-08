import os
with open('app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Insert helper
code = '''def _cleanup_media_files(urls: List[str]):
    if not urls:
        return
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
'''
text = text.replace('def _require_project_access(', code + '\n\ndef _require_project_access(') 

# 2. delete_project
old_dp = '''        raise HTTPException(status_code=500, detail=str(e))

    # Best-effort file cleanup after DB commit
    try:
        upload_root = settings.UPLOAD_DIR
        if not os.path.isabs(upload_root):
            upload_root = os.path.abspath(upload_root)

        def _to_upload_path(url_or_path: str) -> Optional[str]:
            if not url_or_path:
                return None
            raw = str(url_or_path).strip()
            if not raw:
                return None

            # If it's a URL, strip scheme/host
            try:
                parsed = urllib.parse.urlparse(raw)
                path_part = parsed.path if parsed.scheme else raw
            except Exception:
                path_part = raw

            path_part = urllib.parse.unquote(path_part)
            path_part = path_part.lstrip("/")

            # Normalize common forms:
            # - uploads/<user>/<file>
            # - /uploads/<user>/<file>
            # - <user>/<file> (relative already)
            if path_part.startswith("uploads/"):
                rel = path_part.replace("uploads/", "", 1)
            elif "/uploads/" in path_part:
                rel = path_part.split("/uploads/", 1)[1]
            else:
                rel = path_part

            abs_path = os.path.abspath(os.path.join(upload_root, rel))
            # Safety: only delete within upload_root
            if not abs_path.startswith(upload_root):
                return None
            return abs_path

        for u in set(candidate_urls):
            p = _to_upload_path(u)
            if p and os.path.exists(p) and os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception as fe:
                    logger.warning(f"[delete_project] Failed to delete file {p}: {fe}")
    except Exception as e:
        logger.warning(f"[delete_project] File cleanup skipped/failed project_id={project_id}: {e}")

    return None'''
new_dp = '''        raise HTTPException(status_code=500, detail=str(e))

    # Best-effort file cleanup after DB commit
    _cleanup_media_files(candidate_urls)

    return None'''
text = text.replace(old_dp, new_dp)

# 3. delete_scene
old_ds = '''    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    db.delete(db_scene)
    db.commit()
    return None'''
new_ds = '''    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    candidate_urls = []
    shots = db.query(Shot).filter(Shot.scene_id == scene_id).all()
    for s in shots:
        if s.image_url: candidate_urls.append(s.image_url)
        if s.video_url: candidate_urls.append(s.video_url)

    db.delete(db_scene)
    db.commit()
    
    _cleanup_media_files(candidate_urls)
    
    return None'''
text = text.replace(old_ds, new_ds)

# 4. delete_shot
old_dsh = '''    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    db.delete(db_shot)
    db.commit()
    return {"ok": True}'''
new_dsh = '''    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    candidate_urls = []
    if db_shot.image_url: candidate_urls.append(db_shot.image_url)
    if db_shot.video_url: candidate_urls.append(db_shot.video_url)

    db.delete(db_shot)
    db.commit()
    
    _cleanup_media_files(candidate_urls)
    
    return {"ok": True}'''
text = text.replace(old_dsh, new_dsh)

# 5. delete_entity
old_de = '''    _require_project_access(db, entity.project_id, current_user, owner_only=True)

    db.delete(entity)
    db.commit()
    return {"status": "success"}'''
new_de = '''    _require_project_access(db, entity.project_id, current_user, owner_only=True)

    candidate_urls = []
    if entity.image_url: candidate_urls.append(entity.image_url)

    db.delete(entity)
    db.commit()
    
    _cleanup_media_files(candidate_urls)
    
    return {"status": "success"}'''
text = text.replace(old_de, new_de)

# 6. delete_project_entities
old_dpe = '''    _require_project_access(db, project_id, current_user, owner_only=True)

    db.query(Entity).filter(Entity.project_id == project_id).delete()    
    db.commit()
    return {"status": "success", "message": "All entities deleted"}'''
new_dpe = '''    _require_project_access(db, project_id, current_user, owner_only=True)

    entities = db.query(Entity).filter(Entity.project_id == project_id).all()
    candidate_urls = [e.image_url for e in entities if e.image_url]

    db.query(Entity).filter(Entity.project_id == project_id).delete()    
    db.commit()
    
    _cleanup_media_files(candidate_urls)
    
    return {"status": "success", "message": "All entities deleted"}'''
text = text.replace(old_dpe, new_dpe)

# 7. delete_asset
old_da = '''    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Delete file if local
    try:
        if asset.url and "/uploads/" in asset.url:
            # parsing logic: /uploads/{user_id}/{filename}
            parts = asset.url.split("/uploads/")
            if len(parts) > 1:
                rel_path = parts[1] # user_id/filename
                file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
        elif asset.url:
            oss_storage_service.delete_url(asset.url)
    except Exception as e:
        print(f"Error deleting file for asset {asset_id}: {e}")

    db.delete(asset)
    db.commit()
    return {"status": "success"}'''
new_da = '''    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    candidate_urls = []
    if asset.url:
        candidate_urls.append(asset.url)

    db.delete(asset)
    db.commit()
    
    _cleanup_media_files(candidate_urls)
    
    return {"status": "success"}'''
text = text.replace(old_da, new_da)

# 8. batch_delete_assets
old_bda = '''    assets = db.query(Asset).filter(
        Asset.id.in_(asset_ids),
        Asset.user_id == current_user.id
    ).all()

    deleted_count = 0
    for asset in assets:
        # Delete file if local
        try:
            if asset.url and "/uploads/" in asset.url:
                parts = asset.url.split("/uploads/")
                if len(parts) > 1:
                    rel_path = parts[1]
                    file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            elif asset.url:
                oss_storage_service.delete_url(asset.url)
        except Exception as e:
            print(f"Error deleting file for asset {asset.id}: {e}")

        db.delete(asset)
        deleted_count += 1

    db.commit()
    return {"status": "success", "deleted_count": deleted_count}'''
new_bda = '''    assets = db.query(Asset).filter(
        Asset.id.in_(asset_ids),
        Asset.user_id == current_user.id
    ).all()

    candidate_urls = []
    deleted_count = 0
    for asset in assets:
        if asset.url:
            candidate_urls.append(asset.url)
        db.delete(asset)
        deleted_count += 1

    db.commit()
    
    _cleanup_media_files(candidate_urls)
    
    return {"status": "success", "deleted_count": deleted_count}'''
text = text.replace(old_bda, new_bda)

with open('app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
