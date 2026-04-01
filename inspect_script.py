import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()
    
idx_collab = text.find('isCreateCollaboratorsCollapsed')

start = text.rfind('<div', 0, idx_collab)
for i in range(5):
    start = text.rfind('<div', 0, start)
print(text[start:start+2500])

