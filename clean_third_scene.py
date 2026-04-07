import re

with open('backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Clean the duplicate Role and Version tags
text = text.replace(
"""# Role: AI Visual Analysis Master & Structured Data Generator
# Version: 2026-03-01-concise

## 最终目标

### 1. 核心底线与实体输出规范 (Core & Outputs)
# Role: AI Visual Analysis Master & Structured Data Generator
# Version: 2026-03-01-concise""",
"""# Role: AI Visual Analysis Master & Structured Data Generator
# Version: 2026-03-01-concise

## 最终目标

### 1. 核心底线与实体输出规范 (Core & Outputs)"""
)

# 2. Clean the repetition of '- **对话与旁白零删减...'.
# Keep only the first comprehensive one under "Language & Context" or top rules.
text = re.sub(r'- \*\*对话与旁白零删减（SUPREME）\*\*：所有的对话，旁白，画外音，独白都要原样写入 beat 中，不允许删减。\n', '', text)
text = re.sub(r'- \*\*对话与旁白零删减\*\*：所有的对话，旁白，画外音，独白都要原样写入 beat 中，不允许删减。\n', '', text)

# 3. Clean up the placeholder "- 模板已合并到本文件（Merged In-File, Authoritative）。" in Prop and Character prompt templates
text = re.sub(r'- 模板已合并到本文件（Merged In-File, Authoritative）。\n', '', text)

with open('backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)

print("Third structural cleanup applied.")
