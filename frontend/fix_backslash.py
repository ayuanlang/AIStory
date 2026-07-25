import re
path = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('\\\'', \"'\")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed backslashes!')
