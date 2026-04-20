import re

with open('backend/app/core/prompts/skills/shot_generation.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('划分为五大维度：', '划分为四大维度：')

new_section_2 = """  2. **按时间编排的运镜与动作流 (Chronological Camera & Action)**：此部分无需大写维度标签，直接以 (P1), (P2) 等动作段落切分，将运镜与动作在同一时间线上融合描写：
     - **以时间线或动作段落(Px)推进**：将本镜内容依据时间线严格划分为 (P1) (P2) 等主节拍顺序推进。在 (P1) 中，必须写明此时的角色动作，以及对应的运镜如何配合；在 (P2) 中写明动作的新阶段及运镜的跟进或转折。**绝不要把运镜和动作分开写**。
     - **明确景别与时空连贯闭环**：必须在运镜描写中**明确写出角色当前所处的动态景别及其演变**（如 `maintaining a Medium Shot`, `pushing into a Close-up` 等），并明确机位“从哪里”移动“到哪里”（严禁机位轴线的无理跳跃）。
     - **相对运动与运镜手法**：必须准确描写“机位运镜”与“角色运动”相叠加后的结果。必须写明具体的运镜手法（如 `Dolly In`, `Whip Pan`）和**物理光学参数变化**。若涉及焦段推拉或景深焦点转换，必须详细交代演变过程，并携带明确的速率副词（`slowly`, `suddenly` 等）。
     - **过渡手法的视听落地**：若该镜为非首镜，必须在动作推进中体现上游【Beat切换说明】中所定义的过渡手法。例如，若上游指定"人物视线相交"作为切换策略，则动作链条中必须包含视线对接的具体过程；若指定"自然推拉过渡"，则必须表现机位或角色的自然延伸。
     - **精准主体与动作细节（强制）**：必须极度明确当前动作的执行主体，严禁使用“He/She/It/They”等独立代词。若是描述“全场震惊”等集体行为，绝不能让所有人做出完全一样的动作表情；坚决摒弃“逃跑”、“战斗”等抽象词，必须将动作拆解为具体的肢体发力方向、微表情变化和空间位移。
     - **环境资产的动态标定与切换声明（强制）**：在对 (P1), (P2) 等各自段落进行描写时，必须明确写出与之关联的环境实体标签（如 `ENV:[Name]`）。若镜头在摇摄中导致画面**背景环境发生变化**，则必须在其发生切换的 (Px) 处明确指出，并交代新的环境关系。
     - **对白语音显式标注（强制）**：凡出现 `Dialogue/OS/V.O.`，必须使用统一语音标签：`(voice_type: ..., tone: ..., speed: ..., volume: ...)` 。
     - **音频与音效同步 (Audio & SFX)**：若存在环境音效（如玻璃碎裂）或音乐重音点，必须在动作节奏中自然融入（例如 `syncing with the sound of glass shattering`），实现音画对齐。"""

old_start = text.find('  2. **`[Camera Movement]` (轨迹、景别速率与光学参数动态变化)**：')
old_end = text.find('  4. **`[Dynamic Atmosphere]`')

if old_start != -1 and old_end != -1:
    text = text[:old_start] + new_section_2 + "\n" + text[old_end:]
    print('Found section to replace.')

text = text.replace('  4. **`[Dynamic Atmosphere]`', '  3. **`[Dynamic Atmosphere]`')
text = text.replace('  5. **`[Text Rendering]`', '  4. **`[Text Rendering]`')

with open('backend/app/core/prompts/skills/shot_generation.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done replacing.")
