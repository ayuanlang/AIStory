import sys

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all lines that append to metaParts with empty strings
import re
new_text = re.sub(r'^\s*(?:if\s*\([^)]*\)\s*)?metaParts\.push\(.*?\);\s*$', '', text, flags=re.MULTILINE)

# Replace the block that builds final string
new_text = re.sub(r'if\s*\(metaParts\.length\s*>\s*0\)\s*\{[^}]*finalSubjectIndexText\s*=\s*\$\{metaParts\.join\([^}]*\)\}\n\n.*?\}\s*', '', new_text, flags=re.DOTALL)

new_text = re.sub(r'if\s*\(metaParts\.length\s*>\s*0\)\s*\{[^}]*content\s*=\s*\$\{header\}\\n.*?\n\n.*?\n\n.*?\s*\}\s*', '', new_text, flags=re.DOTALL)

if new_text != text:
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Stripped metaParts from ScriptEditor.jsx')
else:
    print('No changes made to ScriptEditor.jsx')

