import re
path = 'backend/app/core/prompts/skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md'
content = open(path, encoding='utf8').read()

old4 = r'\*\*群演/无具体剧情角色（优先延迟，§12）\*\*：群演簇、龙套、开场段尚无具体对白/主动作/关键交互者，\*\*尽量不要\*\*标「开场即在场」——优先「待入画 Beat \+ 触发 \+ 具名出入口」，于合适 Beat 再用动作描述入画；开场优先只排叙事焦点与已有剧情功能的具名角色（宏观群体/原文明示已在场/礼法同框必需者除外）。'
new4 = '**群演/无具体剧情角色（特例推迟，§12）**：群演簇、龙套等作为特例可以不标「开场即在场」——可标「待入画 Beat + 触发 + 具名出入口」，于合适 Beat 靠剧情动作描述入画协助分散开场建置压力。但具名角色与主要角色必须按开场全员建置规定硬性处理。'

content = re.sub(old4, new4, content, flags=re.DOTALL)

open(path, 'w', encoding='utf8').write(content)
print('Done!')
