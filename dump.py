import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('isCreating && (')
if idx != -1:
    end_idx = text.find(')', idx + 5000) # That's risky
    print(text[idx:idx+5500])
