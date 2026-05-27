import json
import os
import re

path = r'c:\AS\AIStory\backend\app\core\prompts\skills\scene_analysis_feature_stack\entity_design.md'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

s1 = text.find('## 二、 角色与人物专项规范')
s2 = text.find('## 三、 环境专项规范')
s3 = text.find('## 四、 道具专项规范')
s4 = text.find('## 五、 特殊资产规范')
s5 = text.find('## 六、输出模板（严格）')

common_head = text[:s1]
# Adjust common_head Node 4 part
common_head = common_head.replace('`characters`、`props`、`environments`、`posters` 必须逐条覆盖', '生成的数组必须逐条覆盖')
common_head = common_head.replace('`character -> characters[]`，`prop -> props[]`，`environment -> environments[]`，`cover_poster -> posters[]`', '对应目标的数组')
common_head = common_head.replace('四大数组', '对应数组')

char_part = text[s1:s2]
env_part = text[s2:s3]
prop_part = text[s3:s4]
poster_part = text[s4:s5]
common_tail = text[s5:]

def make_tail(target_key, target_desc, example_json_str):
    tail = common_tail
    tail = re.sub(
        r'全文仅输出\*\*唯一的一个大 JSON 代码块\*\*，里面需完整包含.*?\n',
        f'全文仅输出**唯一的一个大 JSON 代码块**，里面只需包含 `{target_key}`（{target_desc}）。\n',
        tail
    )
    tail = re.sub(
        r'\-\s*\*\*四段结构保底规则.*?\n',
        f'- **单段结构保底规则**：最终 JSON 顶层必须存在 `{target_key}` 数组键。无实体时输出空数组 `[]`。\n',
        tail
    )
    tail = re.sub(
        r'根节点固定含 `characters`、`props`、`environments`、`posters` 四键；',
        f'根节点固定含 `{target_key}` 键；',
        tail
    )
    tail = re.sub(
        r'以下为 characters, props, environments, posters 的合成形态示例：',
        f'以下为 {target_key} 的形态示例：',
        tail
    )
    
    json_start = tail.find('```json\n{')
    json_content_start = tail.find('{', json_start)
    json_end = tail.find('}\n```', json_start) + 1
    
    if json_start != -1 and json_end != -1:
        new_json = '{\n  "' + target_key + '": ' + example_json_str + '\n}'
        tail = tail[:json_start] + '```json\n' + new_json + '\n```\n'
        
    return tail

json_start = common_tail.find('{\n  "characters"')
json_end = common_tail.rfind('\n}') + 2
json_str = common_tail[json_start:json_end]

char_ex = '[]'
prop_ex = '[]'
env_ex = '[]'
poster_ex = '[]'

try:
    data = json.loads(json_str)
    char_ex = json.dumps(data.get('characters', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
    prop_ex = json.dumps(data.get('props', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
    env_ex = json.dumps(data.get('environments', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
    poster_ex = json.dumps(data.get('posters', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
except Exception as e:
    print('Failed to parse json:', e)

with open(path.replace('.md', '_character.md'), 'w', encoding='utf-8') as f:
    f.write(common_head + char_part + make_tail('characters', '角色', char_ex))

with open(path.replace('.md', '_environment.md'), 'w', encoding='utf-8') as f:
    f.write(common_head + env_part + make_tail('environments', '场景', env_ex))

with open(path.replace('.md', '_prop.md'), 'w', encoding='utf-8') as f:
    f.write(common_head + prop_part + make_tail('props', '道具', prop_ex))

with open(path.replace('.md', '_poster.md'), 'w', encoding='utf-8') as f:
    f.write(common_head + poster_part + make_tail('posters', '封面海报', poster_ex))

print('Split complete with refined JSON tails.')
