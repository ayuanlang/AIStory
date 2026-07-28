import re
path = 'backend/app/core/prompts/skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md'
content = open(path, encoding='utf8').read()

old3 = r'\*\*群演/无具体剧情角色延迟入画（优先，降低开场拥挤）\*\*：对\*\*群演簇、龙套、仅气氛/背景功能、本场开场段尚无具体对白/主动作/关键交互\*\*的角色——\*\*尽量不要\*\*在 Scene 首拍/开场建置即写入画内；优先标为【Scene实体覆盖】「待入画 Beat \+ 触发 \+ \*\*具名出入口\*\*」'
new3 = '**群演/无具体剧情角色可推迟入画（降低开场拥挤的特例）**：对**群演簇、龙套、仅气氛/背景功能且剧情未强制要求立刻出场**的角色——**可以作为特例**不在 Scene 首拍/开场建置即写入画内；可标为【Scene实体覆盖】「待入画 Beat + 触发 + **具名出入口**」'

content = re.sub(old3, new3, content, flags=re.DOTALL)

open(path, 'w', encoding='utf8').write(content)
print('Done!')
