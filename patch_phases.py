import sys
path = 'C:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    "phase: 'analyzing'": "phase: 'analyzing_scene'",
    "phase: 'importing'": "phase: 'saving_scenes'",
    "phase: 'checking_scene_subjects'": "phase: 'generating_assets'",
    "phase: 'supplementing_scene_subjects'": "phase: 'importing_assets'",
    "phase === 'analyzing'": "phase === 'analyzing_scene'",
    "phase === 'importing'": "phase === 'saving_scenes'",
    "phase === 'checking_scene_subjects'": "phase === 'generating_assets'",
    "phase === 'supplementing_scene_subjects'": "phase === 'importing_assets'"
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated phases")
