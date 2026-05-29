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

base_common_head = text[:s1]
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
    json_end = tail.find('}\n```', json_start) + 1
    
    if json_start != -1 and json_end != -1:
        new_json = '{\n  "' + target_key + '": ' + example_json_str + '\n}'
        tail = tail[:json_start] + '```json\n' + new_json + '\n```\n'
        
    return tail

def make_head(target_key, target_name):
    head = base_common_head
    old_core = re.search(r'## 核心任务\n.*?不再负责剧情切片、动作编排或实体抽取。', head, re.DOTALL)
    if old_core:
        new_core = f'## 核心任务\n本部分具体目标是进行**{target_name}类**的实体设计。你**仅负责且只能负责**针对上游 `Subject Index` 中的 `{target_name}` 类别实体进行美术设计、规范化与镜头转译，并最终无损封装为你专属的 JSON 数组（`{target_key}`）；不再负责剧情切片、动作编排或实体抽取，也**绝不**处理其他类型的实体设计的任务。'
        head = head.replace(old_core.group(0), new_core)

    head = head.replace('`characters`、`props`、`environments`、`posters` 必须逐条覆盖', f'生成的 `{target_key}` 数组必须逐条覆盖')
    head = head.replace('`character -> characters[]`，`prop -> props[]`，`environment -> environments[]`，`cover_poster -> posters[]`', f'相应的目标数组（{target_key}）')
    head = head.replace('四大数组', '对应数组')
    return head

json_start = common_tail.find('{\n  "characters"')
json_end = common_tail.rfind('\n}') + 2
json_str = common_tail[json_start:json_end]

char_ex = prop_ex = env_ex = poster_ex = '[]'
try:
    data = json.loads(json_str)
    char_ex = json.dumps(data.get('characters', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
    prop_ex = json.dumps(data.get('props', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
    env_ex = json.dumps(data.get('environments', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
    poster_ex = json.dumps(data.get('posters', []), ensure_ascii=False, indent=4).replace('\n', '\n  ')
except Exception as e:
    pass

with open(path.replace('.md', '_character.md'), 'w', encoding='utf-8') as f:
    f.write(make_head('characters', '角色') + char_part + make_tail('characters', '角色', char_ex))

with open(path.replace('.md', '_environment.md'), 'w', encoding='utf-8') as f:
    f.write(make_head('environments', '场景') + env_part + make_tail('environments', '场景', env_ex))

with open(path.replace('.md', '_prop.md'), 'w', encoding='utf-8') as f:
    f.write(make_head('props', '道具') + prop_part + make_tail('props', '道具', prop_ex))

with open(path.replace('.md', '_poster.md'), 'w', encoding='utf-8') as f:
    f.write(make_head('posters', '封面海报') + poster_part + make_tail('posters', '封面海报', poster_ex))

print('Split rewritten.')