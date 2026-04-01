import sys
import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('setIsCreateCollaboratorsCollapsed', 70000)
end_idx = text.find('</motion.div>', idx)
if idx != -1:
    print(text[idx-500:end_idx+200])

