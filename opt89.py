import re

new_text = '''### 八、静态提示词要求（Start, Keyframes & End Frames）
1. **基础定义**：`Start Frame` 为T=0稳定静态，`End Frame` 为动作落定终局。`Keyframes` 为变阶段关键截帧（无则填 `NO`）。
2. **视觉基线服从**：光影色温须先服从项目全局视觉定位（例如禁将治愈系拍成死黑，惊悚拍成全白等）。
3. **剧情必要实体闭环 (强制)**：维持叙事的角色(CHAR)、道具(PROP)、环境(ENV)，必须在首帧交代起点，在动态反映过程变化，在尾帧定格终点。严禁资产前后断裂。
4. **特效相位静态定格**：若有特效，首/关键/尾帧必须写明当时的 `effect_phase`、强度等级、可见物理遗留表现。
5. **绝对客观可视化**：像描写单张相片一样，**严禁描写含有时间经过的动作**，彻底剥离前后剧情带来的主观形容词（拒写“悲伤回忆”，改写为具体的“微蹙眉角平视”）。
6. **视觉连续性校验法则 (强制)**：本镜 `Start Frame` 必须绝对接续上镜 `End Frame` 的结果状态环境定位，角色前后景(FG/MG/BG)、姿态及空间朝向。
7. **首尾帧六大维度排布**：
   - `[Global Style]`：总视觉定位必须写入。
   - `[Context & Lighting]`：交代明确光源照射及其对微表情的可见度保护。包含多光混合时的肤色保护声明。
   - `[Camera & Composition]`：明确景别(Full Shot等)和构图。
   - `[Staging & Spatial]`：角色必须依靠ENV锚点定位，细化占位侧、躯体朝向与手部接触关系。
   - `[Subject Action (Static)]`：物理状态凝固，严格写肢体、表情、不写主观心情。严禁存在微动位移。
   - `[Lighting & Tone Consistency (Static)]`：写明光线定调与阶段映射。固定句式："起始光线：[参数],对应角色的 [情感/阶段]；终止光线：[参数],强化了 [转折结果]"。
   - `[Layers & Details]`：层级与细节驻留呈现。

### 九、最终标准输出 (Final Output Format)
- 你只需输出最终的一张 Markdown 表格即可。
- **严禁输出任何开场白、反思过程或表外寒暄**。

#### Markdown 表头格式与双语编写约束
- **双语同步与资产保留**：对应带 `(CN)` 的中文列必须使用符合中文语境的自然语言精准翻译。中文列中严禁维度的英文标签，但**必须强制保留所有带方括号的实体标签**（如 `CHAR:[@Name]`，绝对不要翻译或用代词替换）。
- **静态单一铁律**：首尾静态帧每帧由于不可携带时间流逝，绝对只能描写单一确认的静止空间环境。不得存在时空过渡或场景切换动作。只有 `Video Content` 中才允许时空跨度过渡。
- **逻辑推演 (Shot Logic)**：纯中文推理。**强制连贯前接判定**：开头必须先明确写出紧承上一镜 `End Frame` 尾态，说明使用了何种运镜/走位【过渡手法】。然后需附带时间预估(如 P1()+P2()= )。首镜则需解说"开场抓力"。
- **明确时长**：`Duration (s)` 只填整数秒。
- **光线色调映射交织编排**：上述要求的“光线联动情感”内容直接写到对应的静态首尾帧或对应的视频动态文本块中进行声明陈述。

| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | Keyframes (CN) | End Frame (CN) | Associated Entities |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| (自动生成) | (核心动作简述) | (当前场景ID) | (前接状态+转场手法+分段耗时加法公式等内容) | (纯相片纯物理静止推断，不可见剧情词或行动动词，只填这六个维度的组合文本...) | (按时序排列的运镜交互动作推断文本...) | (整数秒数) | (关键静止截图推断) | (动作落定的静止物理相片推断...) | (对应 Start Frame 的优质中文语境文本，但要求完整带入英文标签和变量参数) | (对应 Video Content 中文文本) | (对应 Keyframes 中文文本) | (对应 End Frame 中文文本) | (该镜头涉及的 `CHAR`, `PROP`, `ENV` 标签列表) |

'''

with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'(### 八、.*?)$', text, re.DOTALL)
if m:
    with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'w', encoding='utf-8') as f:
        f.write(text[:m.start()] + new_text)
    print('Applied sec 8-9')
else:
    print('Pattern not found')
