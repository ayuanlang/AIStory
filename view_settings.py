import re

with open('frontend/src/pages/Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

for match in re.finditer(r'activeTab === \S+? [?&][&]?', text):
    print(match.group(0))
