import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = '''            if temp_url.startswith("http"):
                await asyncio.to_thread(_bind_generated_media_to_shot, db, current_user, req, temp_url, False)
                await asyncio.to_thread(_register_asset_helper, db, current_user.id, temp_url, req, result.get("metadata"))'''

new_block = '''            if temp_url.startswith("http"):
                await asyncio.to_thread(_bind_generated_media_to_shot, db, current_user, req, temp_url, False)
                if not _is_ephemeral_provider_media_url(temp_url):
                    await asyncio.to_thread(_register_asset_helper, db, current_user.id, temp_url, req, result.get("metadata"))'''

text = text.replace(old_block, new_block)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Video Asset patched')
