with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('if (onLog) onLog(Superuser  submit: prompt preview opened before submission., \'info\');', 'if (onLog) onLog(Superuser  submit: prompt preview opened before submission., \'info\');') 
text = text.replace('throw new Error(Superuser canceled  prompt confirmation.);', 'throw new Error(Superuser canceled  prompt confirmation.);') 
text = text.replace('message: t(正在执行 , Running ),', 'message: t(正在执行 ..., Running ...),') 
with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f: 
    f.write(text) 
