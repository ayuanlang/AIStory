import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "isCreateSceneAnalysisCollapsed" in line or "isCreateManagementCollapsed" in line or "isCreateCollaboratorsCollapsed" in line:
        print(f"Line {i+1}: {line.strip()}")
