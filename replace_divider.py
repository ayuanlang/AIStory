import re

file_path = 'c:/AIStory/backend/app/core/prompts/scene_analysis.txt'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '版式控制语句；generation_prompt_en 必须明确写出 keep the four panels directly',
    '版式控制语句，并明确强调宫格间不要有任何可见分割线；generation_prompt_en 必须明确写出 
o visible divider lines between panels 以及保留 keep the four'
)
text = text.replace(
    '版式控制语句；generation_prompt_en 必须明确写出 keep the four panels',
    '版式控制语句，并明确强调各宫格之间不要有可视分割线；generation_prompt_en 必须同时明确写出 
o visible divider lines between panels 以及保留 keep the four panels'
)


text = text.replace(
    '四格，且整张资产表必须对齐系统',
    '四格（必须保证宫格之间没有任何画出来的分割线、边框或缝隙），且整张资产表必须对齐系统'
)

text = text.replace(
    '纯白背景，版式干净，便于资产复用。', 
    '纯白背景，各宫格间不要有分割线，版式干净，便于资产复用。'
)
text = text.replace(
    '纯白背景，版式清晰，适配角色资产管理。', 
    '纯白背景，各宫格间不要有分割线，版式清晰，适配角色资产管理。'
)
text = text.replace(
    '纯白背景，画面干净，角色资产识别清晰。', 
    '纯白背景，各宫格间不要有分割线，画面干净，角色资产识别清晰。'
)

text = text.replace(
    'production-ready character-sheet clarity.',
    'no visible dividers between panels, production-ready character-sheet clarity.'
)
text = text.replace(
    'clean technical character-sheet presentation.',
    'no visible dividers between panels, clean technical character-sheet presentation.'
)
text = text.replace(
    'clean character-sheet composition.',
    'no visible dividers between panels, clean character-sheet composition.'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Replacements done.')
