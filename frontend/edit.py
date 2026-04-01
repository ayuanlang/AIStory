import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "{ key: 'character', label: t('角色', 'Char'), title: t('角色', 'Characters') },\n                            { key: 'environment', label: t('环境', 'Env'), title: t('环境', 'Environments') },\n                            { key: 'prop', label: t('道具', 'Prop'), title: t('道具', 'Props') },",
    "{ key: 'character', label: t('角色', 'Char'), title: t('角色', 'Characters') },\n                            { key: 'environment', label: t('环境', 'Env'), title: t('环境', 'Environments') },\n                            { key: 'prop', label: t('道具', 'Prop'), title: t('道具', 'Props') },\n                            { key: 'poster', label: t('海报', 'Poster'), title: t('封面海报', 'Cover Poster') },"
)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced array")
