import re
with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace _bind_generated_media_to_shot callers
# First in the immediate endpoints where it's first created (temporary URL)
text = re.sub(
    r'_bind_generated_media_to_shot\(db, current_user, request, str\(remote_url\)\)',
    r'_bind_generated_media_to_shot(db, current_user, request, str(remote_url), oss_uploaded_success=False)',
    text
)
# And in the backgrounds on success
text = re.sub(
    r'_bind_generated_media_to_shot\(bg_db, user, req, final_oss_url\)',
    r'_bind_generated_media_to_shot(bg_db, user, req, final_oss_url, oss_uploaded_success=True)',
    text
)

# Replace _bind_generated_media_to_entity callers
text = re.sub(
    r'_bind_generated_media_to_entity\(db, current_user, request, str\(remote_url\)\)',
    r'_bind_generated_media_to_entity(db, current_user, request, str(remote_url), oss_uploaded_success=False)',
    text
)

text = re.sub(
    r'_bind_generated_media_to_entity\(bg_db, user, req, final_oss_url\)',
    r'_bind_generated_media_to_entity(bg_db, user, req, final_oss_url, oss_uploaded_success=True)',
    text
)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Callers patched')
