import sys
import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('setIsCreateCollaboratorsCollapsed')
if idx != -1:
    print(text[idx-500:idx+1500])
