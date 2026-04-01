import sys
import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

match = re.search(r'(<div[^>]*>[\s\S]*?isCreateCollaboratorsCollapsed.*?\(\) => setIsCreateCollaboratorsCollapsed[\s\S]*?</button>[\s\S]*?<div className="mt-4 border-t border-white/10 pt-3">[\s\S]*?isCreateTechVisualCollapsed)', text)
if match:
    print(match.group(0)[:800])
else:
    print("Not found")

