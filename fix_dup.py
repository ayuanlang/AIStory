import os

path = 'backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

OLD1 = """                        final_url = norm_url if (norm_url and norm_url != raw_url) else raw_url
                        final_meta = norm_meta if norm_meta is not None else meta
                        
                        if request_mode != "joint_diptych" and not _is_ephemeral_provider_media_url(final_url):"""

NEW1 = """                        final_url = norm_url if (norm_url and norm_url != raw_url) else raw_url
                        final_meta = dict(norm_meta if norm_meta is not None else (meta or {}))
                        if job_id:
                            final_meta["idempotency_key"] = job_id
                        
                        if request_mode != "joint_diptych" and not _is_ephemeral_provider_media_url(final_url):"""

text = text.replace(OLD1, NEW1)

OLD2 = """            else:
                if request_mode != "joint_diptych" and not _is_ephemeral_provider_media_url(temp_url):
                    await asyncio.to_thread(_register_asset_helper, db, current_user.id, temp_url, req, result.get("metadata"))"""

NEW2 = """            else:
                if request_mode != "joint_diptych" and not _is_ephemeral_provider_media_url(temp_url):
                    final_meta_sync = dict(result.get("metadata") or {})
                    if job_id:
                        final_meta_sync["idempotency_key"] = job_id
                    await asyncio.to_thread(_register_asset_helper, db, current_user.id, temp_url, req, final_meta_sync)"""

text = text.replace(OLD2, NEW2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated idempotency_key in endpoints.py')