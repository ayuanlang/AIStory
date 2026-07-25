import re
path = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('alert(\"Script content is too short for analysis.\");', 'if (onLog) onLog(\"Script content is too short for analysis.\", \"error\");')
text = text.replace('alert(t(\"分集失败: \", \"Split failed: \") + (e.message || e));', 'if (onLog) onLog(t(\"分集失败: \", \"Split failed: \") + (e.message || e), \"error\");')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
