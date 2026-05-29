with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('flex gap-4 h-1/3')
end = start + 3000
print(text[start:end])
