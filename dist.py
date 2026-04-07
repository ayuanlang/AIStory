import os

file_path = "backend/app/core/prompts/shot_generator.txt"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith("- **实体引用**："):
        new_lines.append("- **实体与外貌锁定协议 (Entity & Appearance Lockdown, 强制)**：\n")
        new_lines.append("  - 严格使用输入实体，必须与 `Linked Characters`、`Key Props`、`Environment Anchor` 完全一致（包含所有标点、大小写、分隔符等），严禁新造主体名或任何归一化改写。\n")
        new_lines.append("  - **同权与继承**：环境、角色、道具只能继承已定稿规范名。禁止使用别名、同义词。若需换装/环境翻新，回退 Scene 层处理。\n")
        new_lines.append("  - **前缀语法**：角色写 `CHAR:[@Name]`（必须有@），环境写 `ENV:[Name]`（绝不能有@），道具写 `PROP:[Name]`（绝不能有@）。每条生成描述必须含有且正确引用。\n")
        new_lines.append("  - **冻结示例**：若实体名是 `Officer Valerius`，则 `Officer_Valerius` 等全是错误。\n")
        skip = True
    elif line.startswith("- **环境继承权威"):
        skip = False
    
    if not skip:
        new_lines.append(line)

lines = new_lines
new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith("- **OTS 切换强制拆分"):
        new_lines.append("- **OTS 视角切换与分场规则 (OTS Transition Rules, 强制)**：\n")
        new_lines.append("  - **强制拆分Shot**：当 `A over B shoulder` 切到 `B over A shoulder` 时，必须至少拆成两个独立 Shot（视角_01 / 视角_02），并注明 Front/Reverse 关系与机位落点（是否跨线）。\n")
        new_lines.append("  - **强制触发新Scene**：若此切换伴随背景主集合变化、越轴反转或视角重构（如门内看外转为门外看内），必须新起 Scene 并绑定 Environment 变体，严禁同场重构。\n")
        skip = True
    elif line.startswith("- **禁止新造实体"):
        skip = False
        continue # also skip this line
    elif line.startswith("- **上游 Subject Packet"):
        skip = False
    
    if not skip:
        new_lines.append(line)

lines = new_lines
new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith("- **Bracket Safety"):
        skip = True
    elif line.startswith("- **外观锁定"):
        skip = False
        continue # remove Appearance Lockdown
    elif line.startswith("- **生图镜头参数强化"):
        skip = False
        
    if not skip:
        new_lines.append(line)

# Remove Micro-Beat duplicate: \n- **微节拍时长护栏
# Wait we just need to keep one version. We keep it under Duration Management.
# Let's write back
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Rewrite complete")
