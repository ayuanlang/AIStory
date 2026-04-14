import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        request_mode = str(req_context.get("mode") or "").strip().lower()
        if request_mode != "joint_diptych" and normalized_url and not _is_ephemeral_provider_media_url(normalized_url):
            _register_asset_helper(db, current_user.id, normalized_url, req_context, normalized_meta)
            _bind_generated_media_to_shot(db, current_user, req_context, normalized_url, oss_uploaded_success=False)
            _bind_generated_media_to_entity(db, current_user, req_context, normalized_url, oss_uploaded_success=False)
        elif request_mode != "joint_diptych" and normalized_url:'''

replacement = '''        request_mode = str(req_context.get("mode") or "").strip().lower()
        if request_mode != "joint_diptych" and normalized_url and not _is_ephemeral_provider_media_url(normalized_url):
            _register_asset_helper(db, current_user.id, normalized_url, req_context, normalized_meta)
            _bind_generated_media_to_shot(db, current_user, req_context, normalized_url, oss_uploaded_success=True)
            _bind_generated_media_to_entity(db, current_user, req_context, normalized_url, oss_uploaded_success=True)
        elif request_mode != "joint_diptych" and normalized_url:'''

if target in text:
    text = text.replace(target, replacement)
    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched successfully")
else:
    print("Target not found")
