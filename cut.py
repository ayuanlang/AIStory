import sys
import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

# Remove the Scene Analysis dimension block:
scene_analysis_pattern = r'<div className="mt-5 rounded-xl border border-white/10 bg-black/15">\s*<button[\s\S]*?onClick=\{\(\) => setIsCreateSceneAnalysisCollapsed[\s\S]*?\{!isCreateSceneAnalysisCollapsed && \([\s\S]*?</div>\s*\)\}\s*</div>'

# Let's verify how it looks like
idx = text.find("setIsCreateSceneAnalysisCollapsed")
if idx != -1:
    start_tag = text.rfind('<div className="mt-5 rounded-xl border border-white/10 bg-black/15">', 0, idx)
    print("Start tag of Scene Analysis:", start_tag)
    # find the end of this block
    if start_tag != -1:
        # we can just use regex substitution safely if we refine it
        pass

# The Collaborators ("共享与审核") block
idx_collab = text.find("setIsCreateCollaboratorsCollapsed")
if idx_collab != -1:
    start_tag_c = text.rfind('<div className="mt-5 rounded-xl border border-white/10 bg-black/15">', 0, idx_collab)
    print("Start tag of Collaborators:", start_tag_c)

