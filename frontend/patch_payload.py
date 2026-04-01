import re

with open('src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'title: newTitle.trim(),\n            description: newDescription.trim() || null,',
    'title: newTitle.trim(),\n            description: newDescription.trim() || null,\n            has_existing_assets: newHasExistingAssets,'
)

with open('src/pages/ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("done payload update")
