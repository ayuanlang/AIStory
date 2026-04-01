import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('isCreating && (')
if idx != -1:
    print(text[idx+2500:idx+5500])
