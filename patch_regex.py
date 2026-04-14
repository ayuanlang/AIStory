import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('r"^file\d+\.aitohumanize\.com$"', 'r"^file\d*\.aitohumanize\.com$"')
with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('/^file\d+\.aitohumanize\.com$/i', '/^file\d*\.aitohumanize\.com$/i')
with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('/^file\d+\.aitohumanize\.com$/i', '/^file\d*\.aitohumanize\.com$/i')
with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print('Regex patched')
