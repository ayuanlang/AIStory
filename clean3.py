import re

with open('backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Items to remove because they are fully specified in the Rules section.
removals = [
    '整张资产表按 16:9 横向四宫格执行。',
    '整张资产表按 16:9 横向四宫格画布执行。',
    '，四格必须包含面部特征特写、正面全身、侧面全身、背面全身，缺一或非特写起手不可',
    '，四格必须包含微距/局部特写、正面、侧面、背面，缺一或非特写起手不可',
    '禁止退变成照片',
    '要求比例为1:9',
    '禁止血浆、开放伤口等令观众不适内容。',
    '必须完全独立为纯物理空间，无人物动作或遮挡',
    '不可带有情绪/剧情词汇'
]

for r in removals:
    text = text.replace(r, '')

# Cleanup specific trailing empty brackets if created
text = text.replace('()', '').replace('（）', '')

with open('backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)
