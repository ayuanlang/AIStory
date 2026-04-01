import sys
import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

# I want to find the exact block for "场景分析全局维度预设"
idx_scene = text.find('Scene Analysis Settings')
if idx_scene != -1:
    print(text[idx_scene-100:idx_scene+1500])

print("---------------------------------")
idx_collab = text.find('isCreateCollaboratorsCollapsed')
if idx_collab != -1:
    print(text[idx_collab-100:idx_collab+1500])
