import re

with open('backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

removals = [
    '（必须符合全景/中景/特写/高级运镜等闭环要求）',
    '（必须符合上文的黄金比例、女性体态优先级与服饰去平庸规则）',
    '（禁止纯动作罗列）',
    '（禁止主观化臆测）',
    '（禁止写成“看镜头/看我”）',
    '（强制：必须写出焦距与噪点）',
    '（必须以数字标点或括号包围）',
    '（必须符合正反反向、成对事物明确及所有安全规则）',
    '（禁止省略，必须逐条输出全量主体）',
    '（四宫格严苛强制，只允许4个画面，第1格必须是面部特写）',
    '（四视图严苛强制，只允许4个画面，第1格必须是微距/局部特写）',
    '（必须符合前文的真实物理空间、去人物化与最高审美原则）',
    '（必须是纯视觉动作，不带剧情解释）',
    '（禁止出现职业名称，只能写视觉表现）',
    '（必须单列）',
    '（Mandatory）',
    '（Hard Rule）',
    '（SUPREME / 最高准则）'
]

for r in removals:
    text = text.replace(r, '')

text = text.replace('()', '').replace('（）', '')

with open('backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)
