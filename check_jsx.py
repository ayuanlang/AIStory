
with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('return (')
if idx != -1:
    print(text[idx:idx+2500])
else:
    print('Not found')

