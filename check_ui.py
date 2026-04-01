import sys

with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Verify where we are
scene_idx = content.find("Scene Analysis Dimensions")
print("Scene Analysis Dimensions found at:", scene_idx)

collab_idx = content.find("Collaborators")
print("Collaborators found at:", collab_idx)

