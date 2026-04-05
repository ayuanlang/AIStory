# -*- coding: utf-8 -*-
with open('c:/AIStory/backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

import re
old_text_pattern = re.compile(r'### Part 2: Entities JSON \(Strict Schema\).*?严格分配到.*?数组中！', re.DOTALL)
new_text = '''### Part 2: Entities JSON (Strict Schema)

**关于 JSON 格式结构的最高优先级警告 (CRITICAL STRUCTURAL WARNING)**：
在这一部分，必须只输出 **唯一的一个** 完整 JSON 对象。
该对象的根节点必须包含并置的四大键名："characters"、"props"、"environments"、"project_visual_backfill"。
**极端错误警告：绝不能把 "props"、"environments" 和 "封面" 实体塞进 "characters" 数组中！！！请严格根据前序识别出的实体类别分装至对应的三个数组里。**'''

text = old_text_pattern.sub(new_text, text)

with open('c:/AIStory/backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed!')
