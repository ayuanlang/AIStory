import re
path = r'C:\\AIStory\\backend\\app\\core\\prompts\\scene_analysis.txt'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace part 2D
text = text.replace('#### Part 2D — Project Visual Backfill JSON (Mandatory)', '#### Part 2E — Project Visual Backfill JSON (Mandatory)')

text = re.sub(
    r'- 封面环境固定命名规则（Mandatory）：.*?真实输出不得直接复用示例空间。\n- 中文项目普通环境 \+ 封面特殊环境追加示例（Mandatory）：\n',
    '- 单语种示例收口规则（Mandatory）：本节只保留 1 组普通环境 JSON 权威示例。封面请参见 Part 2D。真实输出不得直接复用示例空间。\n- 中文项目语境示例（普通环境示例）：\n',
    text, flags=re.DOTALL
)

# Create Part 2D covers
new_part_2d = '''
#### Part 2D — Covers (封面实体)
- 专属 covers 数组硬规则（Mandatory）：封面输出作为一个特别的 subjects 类型，不放在环境里，进入 covers[] 数组。
- 封面固定命名规则（Mandatory）：封面特制 Scene 对应的实体必须进入 covers[]，并使用固定命名：
ame="封面海报"、
ame_en="Cover Poster"。
- 封面提示词硬规则（Mandatory）：该特殊条目的 generation_prompt_cn/en 必须明确说明采用 4:3 横向海报画布...。
- 封面全量依赖硬规则（Mandatory）：封面的 isual_dependencies 必须包揽实际出现在封面主视觉中的关键角色、道具、基础环境。

`json
{
  "covers": [
    {
      "subject_no": "S004",
      "name": "封面海报",
      "name_en": "Cover Poster",
      "atmosphere": "Premium theatrical tension with dramatic layered poster depth",
      "visual_params": "Poster/Cover/4:3",
      "description_cn": "整集封面海报专用，固定使用 4:3 横向海报画布...",
      "generation_prompt_cn": "电影级写实封面海报，整张画面按 4:3 横向执行。必须显式继承封面涉及的全部关键依靠...",
      "generation_prompt_en": "Premium theatrical cover-poster named Cover Poster...",
      "negative_prompt_en": "comic grid, tiled collage, split-screen montage...",
      "anchor_description": "cover poster layout, upper-middle title safe zone",
      "visual_dependencies": ["CHAR:[@林月]", "CHAR:[@程雾]", "PROP:[证据档案袋]", "ENV:[港口办公室 正向 中景 夜]"],
      "dependency_strategy": {
        "type": "Type A",
        "logic": "Derived as a special cover-poster environment that consolidates every cover-involved key subject..."
      }
    }
  ]
}
`

#### Part 2E — Project Visual Backfill JSON (Mandatory)
'''

text = text.replace('#### Part 2E — Project Visual Backfill JSON (Mandatory)', new_part_2d)

# Regex to remove Cover Poster from environments[] array
text = re.sub(
    r',\s*{\s*"subject_no":\s*"S004",\s*"name":\s*"封面海报".*?}\s*',
    '',
    text, flags=re.DOTALL
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
