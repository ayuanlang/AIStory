import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '<option value="prop">{t(\'道具\', \'Props\')}</option>\n                                <option value="environment">{t(\'环境\', \'Environments\')}</option>',
    '<option value="prop">{t(\'道具\', \'Props\')}</option>\n                                <option value="environment">{t(\'环境\', \'Environments\')}</option>\n                                <option value="poster">{t(\'海报\', \'Poster\')}</option>'
)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced select options")
