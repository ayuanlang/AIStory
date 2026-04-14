import json
with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# _bind_generated_media_to_shot
old_shot = '''def _bind_generated_media_to_shot(db: Session, current_user: User, req: Any, media_url: Optional[str]) -> None:'''
new_shot = '''def _bind_generated_media_to_shot(db: Session, current_user: User, req: Any, media_url: Optional[str], oss_uploaded_success: Optional[bool] = None) -> None:'''
text = text.replace(old_shot, new_shot)

old_shot_body = '''    if asset_type in {"start_frame", "start"}:
        if shot.image_url != media_url:
            shot.image_url = media_url
            changed = True

    elif asset_type in {"end_frame", "end"}:
        tech = {}
        try:
            tech = json.loads(shot.technical_notes or "{}")
            if not isinstance(tech, dict):
                tech = {}
        except Exception:
            tech = {}

        if tech.get("end_frame_url") != media_url:
            tech["end_frame_url"] = media_url
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type == "video":
        if shot.video_url != media_url:
            shot.video_url = media_url
            changed = True

    if not changed:
        return'''
new_shot_body = '''    tech = {}
    try:
        tech = json.loads(shot.technical_notes or "{}")
        if not isinstance(tech, dict):
            tech = {}
    except Exception:
        tech = {}

    if asset_type in {"start_frame", "start"}:
        if shot.image_url != media_url or (oss_uploaded_success is not None and tech.get("start_frame_oss_uploaded") != oss_uploaded_success):
            shot.image_url = media_url
            if oss_uploaded_success is not None:
                tech["start_frame_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type in {"end_frame", "end"}:
        if tech.get("end_frame_url") != media_url or (oss_uploaded_success is not None and tech.get("end_frame_oss_uploaded") != oss_uploaded_success):
            tech["end_frame_url"] = media_url
            if oss_uploaded_success is not None:
                tech["end_frame_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type == "video":
        if shot.video_url != media_url or (oss_uploaded_success is not None and tech.get("video_oss_uploaded") != oss_uploaded_success):
            shot.video_url = media_url
            if oss_uploaded_success is not None:
                tech["video_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    if not changed:
        return'''
text = text.replace(old_shot_body, new_shot_body)

# _bind_generated_media_to_entity
old_ent = '''def _bind_generated_media_to_entity(db: Session, current_user: User, req: Any, media_url: Optional[str]) -> None:'''
new_ent = '''def _bind_generated_media_to_entity(db: Session, current_user: User, req: Any, media_url: Optional[str], oss_uploaded_success: Optional[bool] = None) -> None:'''
text = text.replace(old_ent, new_ent)

old_ent_sig2 = '''    if str(entity.image_url or "").strip() == stable_media_url:'''
new_ent_sig2 = '''    tech_attrs = {}
    try:
        tech_attrs = json.loads(entity.custom_attributes or "{}")
        if not isinstance(tech_attrs, dict): tech_attrs = {}
    except Exception:
        pass

    if str(entity.image_url or "").strip() == stable_media_url and (oss_uploaded_success is None or tech_attrs.get("oss_uploaded_success") == oss_uploaded_success):'''
text = text.replace(old_ent_sig2, new_ent_sig2)

old_ent_body = '''    entity.image_url = stable_media_url
    db.add(entity)
    db.commit()'''
new_ent_body = '''    if oss_uploaded_success is not None:
        tech_attrs["oss_uploaded_success"] = oss_uploaded_success
        entity.custom_attributes = json.dumps(tech_attrs, ensure_ascii=False)
        
    entity.image_url = stable_media_url
    db.add(entity)
    db.commit()'''
text = text.replace(old_ent_body, new_ent_body)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Bind logic patched')
