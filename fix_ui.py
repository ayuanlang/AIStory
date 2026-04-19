import sys
import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Block 1 (around line 3240)
pattern1 = r'''\s*const metaParts = \[\];.*?if \(metaParts\.length > 0\) \{.*?finalSubjectIndexText =.*?\}'''
code = re.sub(pattern1, '', code, flags=re.DOTALL)

# Block 2 (around line 4650)
pattern2 = r'''\s*if \(\!skipMetadata\) \{.*?const metaParts = \[\];.*?if \(metaParts\.length > 0\) \{.*?content =.*?;.*?\}\s*\}'''
code = re.sub(pattern2, '', code, flags=re.DOTALL)

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched ScriptEditor.jsx')
