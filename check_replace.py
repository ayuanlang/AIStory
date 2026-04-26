import os

path = 'backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

OLD1 = """                        final_url = norm_url if (norm_url and norm_url != raw_url) else raw_url
                        final_meta = norm_meta if norm_meta is not None else meta
                        
                        if request_mode != "joint_diptych" and not _is_ephemeral_provider_media_url(final_url):"""

if OLD1 in text:
    print('Still found the old string! Replace failed.')
else:
    print('Replace success!')
