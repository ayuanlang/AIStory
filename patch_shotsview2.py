import re

with open('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

def replacer_video(m):
    if 'function_name:' not in m.group(0):
        return m.group(1) + " function_name: 'generate_videos',"
    return m.group(0)

def replacer_image(m):
    if 'function_name:' not in m.group(0):
        return m.group(1) + " function_name: 'generate_shot_images',"
    return m.group(0)

text = re.sub(r'(generateVideo\([^)]+,\s*\{)', replacer_video, text)
text = re.sub(r'(generateImage\([^)]+,\s*\{)', replacer_image, text)

# ai_generate_shots uses generateSceneShots
def replacer_scene(m):
    if 'function_name:' not in m.group(0):
        return m.group(1) + " function_name: 'generate_shot_images',"
    return m.group(0)

# But wait, ai_generate_shots uses generateSceneShots(sceneId, { ... })
text = re.sub(r'(generateSceneShots\([^)]+,\s*\{)', replacer_scene, text)


with open('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

