import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

idx_scene = text.find("setIsCreateSceneAnalysisCollapsed")
if idx_scene != -1:
    print(text[idx_scene-500:idx_scene])

print("================")

idx_collab = text.find("setIsCreateCollaboratorsCollapsed")
if idx_collab != -1:
    print(text[idx_collab-500:idx_collab])
