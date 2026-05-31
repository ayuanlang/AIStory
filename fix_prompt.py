import re
import os

filepath = r'c:\AS\AIStory\backend\app\core\prompts\skills\scene_analysis_feature_stack\scene_planning_1_script_optimization.md'

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# Remove multiple (强制) if there are too many, but the prompt asked specifically about repetitions & redundancies.

# Let's remove the redundant "仙侠/玄幻" mentions in Node 2 since they are covered in detailed rules.
node2_xianxia_pattern = re.compile(r'\s*- \*\*仙侠/玄幻全局特效量级与配额约束\*\*：.*?(?=\n\s*-)', re.DOTALL)
text = node2_xianxia_pattern.sub('', text)
node2_xianxia_pattern2 = re.compile(r'\s*- \*\*仙侠/玄幻特效篇幅与展开强制前置\*\*：.*?(?=\n\s*-)', re.DOTALL)
text = node2_xianxia_pattern2.sub('', text)

# Remove redundant "风格设计落地到剧本正文" in Node 2 (covered elsewhere)
node2_style_pattern = re.compile(r'\s*- \*\*风格设计落地到剧本正文\*\*：.*?(?=\n\s*-)', re.DOTALL)
text = node2_style_pattern.sub('', text)

# Remove redundant "长动作微动作拆解" and "微表情动作链拆解" in Node 2
node2_action_pattern = re.compile(r'\s*- \*\*长动作微动作拆解\*\*：.*?(?=\n\s*-)', re.DOTALL)
text = node2_action_pattern.sub('', text)
node2_expr_pattern = re.compile(r'\s*- \*\*微表情动作链拆解\*\*：.*?(?=\n\s*-)', re.DOTALL)
text = node2_expr_pattern.sub('', text)

# Remove "Scene 切分与剧本定稿：..." in Node 2
node2_scene_pattern = re.compile(r'\s*- \*\*Scene 切分与剧本定稿\*\*：.*?(\n\n---)', re.DOTALL)
text = node2_scene_pattern.sub(r'\1', text)

# Remove duplicate "基础定位驱动剧情改编" from Node 2
node2_base_pos = re.compile(r'\s*- \*\*基础定位驱动剧情改编\*\*：.*?(?=\n\s*-)', re.DOTALL)
text = node2_base_pos.sub('', text)

# Remove duplicate "结构与间隙补足" from Node 2 since it's covered in "断裂衔接与不合理跳跃补足" and other rules
node2_struct_pattern = re.compile(r'\s*- \*\*结构与间隙补足\*\*：.*?(?=\n\s*(-|\n---))', re.DOTALL)
text = node2_struct_pattern.sub('', text)

# Now, Node 2 is likely almost empty except "核心戏剧视觉化" and maybe Node 1 is also somewhat redundant?
# Let's remove the whole internal expert execution order section if it's just repeating detailed rules.
internal_experts_pattern = re.compile(r'## 🎬 内部专家执行顺序.*?(?=\n---)', re.DOTALL)
text = internal_experts_pattern.sub('', text)

# Remove redundant text from Output format: 
output_long_action = re.compile(r'\n- \*\*长动作拆解要求\*\*：.*?(?=\n- )', re.DOTALL)
text = output_long_action.sub('', text)
output_micro_expr = re.compile(r'\n- \*\*微表情拆解要求\*\*：.*?(?=\n)', re.DOTALL)
text = output_micro_expr.sub('', text)

# Remove duplicate rules from "第三部分：Project Visual Backfill"
backfill_base_pos = re.compile(r'\n- \*\*基础定位驱动与逆定位禁止（强制）\*\*：.*?(?=\n- )', re.DOTALL)
text = backfill_base_pos.sub('', text)
backfill_link = re.compile(r'\n- \*\*字段联动要求（强制）\*\*：.*?(?=\n- )', re.DOTALL)
text = backfill_link.sub('', text)

# And in Section 3 风格设计前置规则
sec3_field_link = re.compile(r'\n- \*\*字段联动要求\*\*：.*?(?=\n- )', re.DOTALL)
text = sec3_field_link.sub('', text)
sec3_base_pos = re.compile(r'\n- \*\*基础定位驱动与逆定位禁止\*\*：.*?(?=\n- )', re.DOTALL)
text = sec3_base_pos.sub('', text)


# Let's consolidate 基础定位 into one definitive rule
text = text.replace('基础定位优先法则：', '基础定位驱动与逆定位禁止：')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Prompt fixed!")
