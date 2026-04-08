import re

with open('app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. delete_project
text = re.sub(
    r'([ \t]+)# Best-effort file cleanup after DB commit.*?([ \t]+)return None',
    r'\g<1># Best-effort file cleanup after DB commit\n\g<1>_cleanup_media_files(candidate_urls)\n\n\g<2>return None',
    text,
    flags=re.DOTALL
)

# 2. delete_scene
text = re.sub(
    r'([ \t]+)_require_project_access\(db, episode\.project_id, current_user, owner_only=True\)\n\n[ \t]+db\.delete\(db_scene\)\n[ \t]+db\.commit\(\)\n[ \t]+return None',
    r'\g<1>_require_project_access(db, episode.project_id, current_user, owner_only=True)\n\n\g<1>candidate_urls = []\n\g<1>shots = db.query(Shot).filter(Shot.scene_id == scene_id).all()\n\g<1>for s in shots:\n\g<1>    if s.image_url: candidate_urls.append(s.image_url)\n\g<1>    if s.video_url: candidate_urls.append(s.video_url)\n\n\g<1>db.delete(db_scene)\n\g<1>db.commit()\n\n\g<1>_cleanup_media_files(candidate_urls)\n\g<1>return None',
    text,
    count=1
)

# 3. delete_shot
text = re.sub(
    r'([ \t]+)_require_project_access\(db, episode\.project_id, current_user, owner_only=True\)\n\n[ \t]+db\.delete\(db_shot\)\n[ \t]+db\.commit\(\)\n[ \t]+return \{"ok": True\}',
    r'\g<1>_require_project_access(db, episode.project_id, current_user, owner_only=True)\n\n\g<1>candidate_urls = []\n\g<1>if db_shot.image_url: candidate_urls.append(db_shot.image_url)\n\g<1>if db_shot.video_url: candidate_urls.append(db_shot.video_url)\n\n\g<1>db.delete(db_shot)\n\g<1>db.commit()\n\n\g<1>_cleanup_media_files(candidate_urls)\n\g<1>return {"ok": True}',
    text,
    count=1
)

# 4. delete_entity
text = re.sub(
    r'([ \t]+)_require_project_access\(db, entity\.project_id, current_user, owner_only=True\)\n\n[ \t]+db\.delete\(entity\)\n[ \t]+db\.commit\(\)\n[ \t]+return \{"status": "success"\}',
    r'\g<1>_require_project_access(db, entity.project_id, current_user, owner_only=True)\n\n\g<1>candidate_urls = []\n\g<1>if entity.image_url: candidate_urls.append(entity.image_url)\n\n\g<1>db.delete(entity)\n\g<1>db.commit()\n\n\g<1>_cleanup_media_files(candidate_urls)\n\g<1>return {"status": "success"}',
    text,
    count=1
)

# 5. delete_project_entities
text = re.sub(
    r'([ \t]+)_require_project_access\(db, project_id, current_user, owner_only=True\)\n\n[ \t]+db\.query\(Entity\)\.filter\(Entity\.project_id == project_id\)\.delete\(\)[ \t]*\n[ \t]+db\.commit\(\)\n[ \t]+return \{"status": "success", "message": "All entities deleted"\}',
    r'\g<1>_require_project_access(db, project_id, current_user, owner_only=True)\n\n\g<1>entities = db.query(Entity).filter(Entity.project_id == project_id).all()\n\g<1>candidate_urls = [e.image_url for e in entities if e.image_url]\n\n\g<1>db.query(Entity).filter(Entity.project_id == project_id).delete()\n\g<1>db.commit()\n\n\g<1>_cleanup_media_files(candidate_urls)\n\g<1>return {"status": "success", "message": "All entities deleted"}',
    text,
    count=1
)

# 6. delete_asset
text = re.sub(
    r'([ \t]+)# Delete file if local.*?db\.delete\(asset\)\n[ \t]+db\.commit\(\)\n[ \t]+return \{"status": "success"\}',
    r'\g<1>candidate_urls = []\n\g<1>if asset.url:\n\g<1>    candidate_urls.append(asset.url)\n\n\g<1>db.delete(asset)\n\g<1>db.commit()\n\n\g<1>_cleanup_media_files(candidate_urls)\n\n\g<1>return {"status": "success"}',
    text,
    flags=re.DOTALL,
    count=1
)

# 7. batch_delete_assets
text = re.sub(
    r'([ \t]+)deleted_count = 0\n[ \t]+for asset in assets:\n[ \t]+# Delete file if local.*?db\.delete\(asset\)\n[ \t]+deleted_count \+= 1\n\n[ \t]+db\.commit\(\)\n[ \t]+return \{"status": "success", "deleted_count": deleted_count\}',
    r'\g<1>candidate_urls = []\n\g<1>deleted_count = 0\n\g<1>for asset in assets:\n\g<1>    if asset.url:\n\g<1>        candidate_urls.append(asset.url)\n\g<1>    db.delete(asset)\n\g<1>    deleted_count += 1\n\n\g<1>db.commit()\n\n\g<1>_cleanup_media_files(candidate_urls)\n\n\g<1>return {"status": "success", "deleted_count": deleted_count}',
    text,
    flags=re.DOTALL,
    count=1
)

with open('app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
