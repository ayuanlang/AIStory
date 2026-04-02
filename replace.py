import re

file_path = 'c:/AIStory/backend/app/core/prompts/scene_analysis.txt'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace 1
text = text.replace(
    '包含"第一宫左侧特写大宫格约占 34%、右侧三宫均分剩余 66%"的版式控制语句',
    '包含"第一宫左侧特写大格，右侧三宫，严格保持横向单排排布的4宫格，绝对不能换行，也不能变成5宫格，右侧三格无需严格均分"等版式控制语句'
)

# Replace 2 (examples in Chinese)
text = text.replace(
    '右侧三宫均分剩余66%', 
    '右侧三宫在剩余 66% 中横向排布（无需强调均分，但绝对禁止换行）'
)
text = text.replace(
    '右侧三宫均分 剩余66%', 
    '右侧三宫在剩余 66% 中横向排布（无需强调均分，但绝对禁止换行）'
)
text = text.replace(
    '右侧正面全身、侧面全身、反面全身三宫均分剩余66%', 
    '右侧正面全身、侧面全身、反面全身三宫横向排布在剩余 66%（无需严格均分，绝对禁止换行）'
)
text = text.replace(
    '右侧66%为三等分结构宫格', 
    '右侧66%为三个结构宫格横向排布（不要求均分，严禁换行）'
)

# Replace 3 (examples in English)
text = text.replace(
    'in equal vertical split', 
    'in a single horizontal row without forcing equal width and strictly no line breaks'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Replacements done.')
