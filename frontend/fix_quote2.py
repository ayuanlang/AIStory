import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'className={px-5 py-2.5 text-xs font-extrabold uppercase rounded-lg transition-all border }',
    'className={px-5 py-2.5 text-xs font-extrabold uppercase rounded-lg transition-all border }'
)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
