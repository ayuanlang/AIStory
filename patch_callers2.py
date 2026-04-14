import re
with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all occurrences where we need to inject the flag
text = re.sub(
    r'_bind_generated_media_to_shot, db, current_user, req, temp_url\)',
    r'_bind_generated_media_to_shot, db, current_user, req, temp_url, False)',
    text
)
text = re.sub(
    r'_bind_generated_media_to_entity, db, current_user, req, temp_url\)',
    r'_bind_generated_media_to_entity, db, current_user, req, temp_url, False)',
    text
)
text = re.sub(
    r'_bind_generated_media_to_shot, bg_db, bg_user, req_obj, norm_url\)',
    r'_bind_generated_media_to_shot, bg_db, bg_user, req_obj, norm_url, True)',
    text
)
text = re.sub(
    r'_bind_generated_media_to_entity, bg_db, bg_user, req_obj, norm_url\)',
    r'_bind_generated_media_to_entity, bg_db, bg_user, req_obj, norm_url, True)',
    text
)

# And also _bind_generated_media_to_xx(db, current_user, req_context, normalized_url) around line 2347
text = re.sub(
    r'_bind_generated_media_to_shot\(db, current_user, req_context, normalized_url\)',
    r'_bind_generated_media_to_shot(db, current_user, req_context, normalized_url, oss_uploaded_success=False)',
    text
)
text = re.sub(
    r'_bind_generated_media_to_entity\(db, current_user, req_context, normalized_url\)',
    r'_bind_generated_media_to_entity(db, current_user, req_context, normalized_url, oss_uploaded_success=False)',
    text
)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Callers patched round 2')
