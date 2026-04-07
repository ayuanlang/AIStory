import re

with open('backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

removals = [
    '(Mandatory)',
    '(Hard Rule)',
    '(SUPREME / 最高准则)'
]

for r in removals:
    text = text.replace(r, '')

text = text.replace('()', '').replace('（）', '')

with open('backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)
