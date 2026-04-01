import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('isCreateSceneAnalysisCollapsed ?')
if idx != -1:
    print(text[idx-500:idx+2000])

print("=--=" * 10)

idx = text.find('isCreateCollaboratorsCollapsed ?')
if idx != -1:
    print(text[idx-500:idx+2000])

