import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern for the single-line ReferenceManager in the video section
pattern = r'(<ReferenceManager shot={editingShot} entities={entities}.*?storageKey="video_ref_image_urls".*?\s*\/>)'

def add_param(match):
    tag = match.group(1)
    if 'additionalAutoRefs' not in tag:
        # insert right before 'storageKey='
        return tag.replace('storageKey="video_ref_image_urls"', 'additionalAutoRefs={usePrevVideo ? [shots[Math.max(0, shots.findIndex(s => s.id === editingShot?.id) - 1)]?.video_url].filter(Boolean) : []} storageKey="video_ref_image_urls"')
    return tag

content = re.sub(pattern, add_param, content)

# Now, wait, is there another one spanning multiple lines?
pattern2 = r'(<ReferenceManager[^>]*storageKey="video_ref_image_urls"[^>]*>.*?</ReferenceManager>|<ReferenceManager[^>]*storageKey="video_ref_image_urls"[^>]*\/>)'

def add_param_multiline(match):
    tag = match.group(1)
    if 'additionalAutoRefs' not in tag:
        return tag.replace('storageKey="video_ref_image_urls"', 'additionalAutoRefs={usePrevVideo ? [shots[Math.max(0, shots.findIndex(s => s.id === editingShot?.id) - 1)]?.video_url].filter(Boolean) : []} storageKey="video_ref_image_urls"')
    return tag

content = re.sub(pattern2, add_param_multiline, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
