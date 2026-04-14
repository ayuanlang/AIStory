import re
with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the isEphemeralProviderMediaUrl call with the inline regex test.
content = content.replace(
    '''isEphemeralProviderMediaUrl(shot.video_url)''', 
    '''/^file\d+\.aitohumanize\.com$/i.test(String(new URL(String(shot.video_url || '').trim(), window.location.origin).hostname || '').trim())'''
).replace(
    '''isEphemeralProviderMediaUrl(shot.image_url)''',
    '''/^file\d+\.aitohumanize\.com$/i.test(String(new URL(String(shot.image_url || '').trim(), window.location.origin).hostname || '').trim())'''
)

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Inlined check in ShotsView')
