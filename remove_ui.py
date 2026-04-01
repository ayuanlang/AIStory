import re

with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to remove Scene Analysis Dimensions
pattern_scene_analysis = r'<div className="mt-5 rounded-xl border border-white/10 bg-black/15">\s*<button\s*type="button"\s*onClick=\{\(\) => setIsCreateSceneAnalysisCollapsed\(\(prev\) => !prev\)\}[\s\S]*?(?:</div>\s*)\}\s*</div>'

new_content = re.sub(pattern_scene_analysis, '', content)

# Pattern to remove sharing and review
pattern_collab = r'<div className="mt-5 rounded-xl border border-white/10 bg-black/15">\s*<button\s*type="button"\s*onClick=\{\(\) => setIsCreateCollaboratorsCollapsed\(\(prev\) => !prev\)\}[\s\S]*?(?:</div>\s*)\}\s*</div>'

new_content = re.sub(pattern_collab, '', new_content)

if content != new_content:
    with open('frontend/src/pages/ProjectList.jsx', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("UI components removed")
else:
    print("Could not find the UI components to remove")
