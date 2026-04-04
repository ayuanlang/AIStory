import sys
file_path = r'c:\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(\"if (onLog) onLog(Failed to start auto AI shots: , 'error');\", \"if (onLog) onLog(\Failed to start auto AI shots: \\, 'error');\")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed backticks!')
