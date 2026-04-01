import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'isCreateSceneAnalysisCollapsed', text)]
for idx in matches:
    print("MATCH AT", idx)
    print(text[idx-200:idx+500])
    print("===")
