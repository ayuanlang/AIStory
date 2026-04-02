import re
with open('frontend/src/pages/Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find(\"activeTab === 'account' && (\")
print(text[idx-200:idx+50])
