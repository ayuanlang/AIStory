import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# For image:
text = re.sub(
    r'if temp_url\.startswith\("http"\) and not _is_ephemeral_provider_media_url\(temp_url\):',
    r'if temp_url.startswith("http"):',
    text
)

# For voice (voice_url):
text = re.sub(
    r'if voice_url\.startswith\("http"\) and not _is_ephemeral_provider_media_url\(voice_url\):',
    r'if voice_url.startswith("http"):',
    text
)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Background upload triggers patched')
