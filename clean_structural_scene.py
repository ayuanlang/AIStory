import sys
import re

with open('backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Clean up "项目类型正向注入规则" (Project Type Positive Injection) in Environment, Character, Prop
# This is already defined in global section:
# "19.1 场景与道具项目类型正向注入规则" and "19. 项目类型-主体一致性硬规则"
# Wait, let's look at the global one:
# "18. 项目类型与定位驱动全局风格..."
# "19. 项目类型-主体一致性硬规则..."
# Let's completely remove the local repetitions since the global one covers them.

text = re.sub(r'- \*\*项目类型正向注入规则[^\n]*\n(?:  - \*\*实拍[^\n]*\n)(?:  - \*\*动漫[^\n]*\n)(?:  - \*\*风格化 3D[^\n]*\n)(?:  - \*\*未命中[^\n]*\n)?', '', text)

# 2. Clean up "正向措辞硬规则" (Positive Phrasing Hard Rule) in Environment, Character, Prop
# It's defined globally in "19.2 场景与道具正向措辞硬规则"
text = re.sub(r'- \*\*正向措辞硬规则[^\n]*\n', '', text)

# 3. "字段语言职责固定 / 字段语言与项目语言沿用总则"
# Delete all those lines that just say "沿用第xx条"
text = re.sub(r'- 字段语言职责固定[^\n]*\n', '', text)
text = re.sub(r'- 字段语言与项目语言沿用总则[^\n]*\n', '', text)

# 4. "角色四宫格版式绝对强制" & "道具四宫格版式绝对强制"
# These are huge blocks locally, but there's a global rule: 
# "- **角色与道具四宫格绝对强制**: 所有角色（character）与所有道具（prop）的 `generation_prompt_cn` 和 `generation_prompt_en` 必须严格采用**四宫格/四视图设定图**格式..."
# Let's remove the redundant huge blocks from 2) Character Prompt Template and 3) Prop Prompt Template
text = re.sub(r'- \*\*角色四宫格版式绝对强制.*?\*\*单格即废稿\*\*。\n', '', text)
text = re.sub(r'- \*\*道具四宫格版式绝对强制.*?\*\*单格即废稿\*\*。\n', '', text)

# 5. Clean up "Fields-to-Prompt Consistency" repeated in Part 2A, 2B, 2C
# They all essentially say: "generation_prompt_xx 必须与上面的几个字段保持显式一致..."
text = re.sub(r'- 字段-提示词一致性硬规则[^\n]*\n', '', text)

with open('backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)

print("Second structural cleanup applied.")
