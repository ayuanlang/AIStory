import re
path = 'backend/app/core/prompts/skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md'
content = open(path, encoding='utf8').read()

old1 = r'\*\*角色建置分布与分批出入画（强制）\*\*：.*?一次建置完毕\*\*\。'
new1 = '**所有角色必须开场建置（严重强调/强制）**：除了**确实是在机位后（需标明不可见，后续切角再落位）或剧情明确规定要在后续Beat由于外力/动作才进场的角色（明确标为待入画并在进场时交代具名出入口）**之外，**所有其他在场角色都必须在场景开场的首个建置段落（或全局建置）中一次性交代清楚所有人的建置落位**。即使角色被分到了不同组别或安排在不同的衍生方位，也不能作为漏建置、推迟建置或拆分到后续Beat进场的借口，**绝对禁止**擅自将原本在场的人拆分到后续 Beat 凭空出场。'

old2 = r'\*\*分批角色入场排期（§16）\*\*：对于\*\*＞3人需逐镜入画\*\*.*?第一拨人。'
new2 = '**角色入场排期与开场亮相（严重强调/强制）**：对于原剧情已明示在场、或从剧情逻辑上开场即属于该场景成员的角色，**无论人数多少，一律需标为「开场即在场」并在开场时完成建置**；**严禁**随意拆分人数让已在场人群“逐镜入画”。只有**剧情明确**由于后续赶到、触发事件才出现的角色，才能标为「待入画 Beat + 触发 + **具名出入口**」。'

content = re.sub(old1, new1, content, flags=re.DOTALL)
content = re.sub(old2, new2, content, flags=re.DOTALL)

open(path, 'w', encoding='utf8').write(content)
print('Done replacement')
