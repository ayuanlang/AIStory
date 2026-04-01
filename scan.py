import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

import re

# 1. Search for Scene Analysis Block
idx_scene = text.find('setIsCreateSceneAnalysisCollapsed')
print("Found Scene Analysis block at:", idx_scene)

# 2. Search for Collaborators Block
idx_collab = text.find('setIsCreateCollaboratorsCollapsed')
print("Found Collaborators block at:", idx_collab)

# 3. Search for Management Block
idx_mgmt = text.find('setIsCreateManagementCollapsed')
print("Found Management block at:", idx_mgmt)

