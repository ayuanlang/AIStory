import re

new_text = '''## 核心目标 (Core Objective)
作为好莱坞级影视分镜大师，将剧本/Beat转化为标准化AI分镜（Shot List）。
**最高限制**：
1. **彻底继承**：强制继承上游输入的所有角色、道具、环境、背景人物及Beat信息，**禁止臆造**。
2. **纯物理定格**：静态帧（Start/End/Keyframe）禁止进行时动作（动作由Video Content承担）。禁止脱离参考图添加外形/材质描绘。
3. **空间挂靠**：所有实体必须明确空间层级（FG/MG/BG）、依靠环境锚点、朝向及接触关系。

---

## 分镜任务 (Storyboard Task)
**任务描述**：按导演确定的剧本与Beat进行标准化分镜拆分及编写。

### 一、输入继承与总控 (Inputs & Semantics)
1. **实体与Beat隔离**：上游给定的角色/道具/群演/场景必须原样复用。群演严禁擅自添戏。必须严格落实相邻Beat的“离镜/入镜”过渡。
2. **项目总控 (Project Context)**：必须全局贯彻项目的 Project Type, Genre, Base Positioning, tone, lighting。
   - **喜剧/日常**：通透光、舒展节奏。
   - **悬疑/动作**：高反差、碎片化运镜。
   - 严禁违背基础定位将所有剧种写成大一统的Noir冷峻风。
3. **时长策略 (Beat 拼合适配)**：单镜强制在 [4, 15] 秒。若上游输入长镜头偏好，须优先合并Beat，使单镜目标时长趋近10s-15s。

### 二、镜头规划与计算 (Shot Planning & Timing)
1. **拆镜推演**：明确场次 -> 切分分镜 -> 确定实体出入画物理闭环（前一步到后一步如何转接）。
2. **首场首镜抓力法则 (Opening Hook)**：全剧首镜必须用极具压迫感或视觉冲击的构图直接承接抓力结构，并在Shot Logic (CN)中写明抓取逻辑。
3. **时长推演公式 (强制 4s-15s)**：
   - **语言耗时**：中文字数 / 4。短句保底1.5s，文戏酌情加停顿。
   - **动作/神态耗时**：常态短发力2-3s。复杂交互4-5s。微表情拆开累加。
   - **总耗时**：串行 = 动作+语言+停顿。并行 = Max(动作, 语言)+停顿。
   - **调平硬规则**：若有预期总时长T，利用比例等比缩放单镜时长，后四舍五入。任何微调仍必须严守 [4, 15] 界线，越界需重新通过拆镜。
4. **切镜客观连续性（禁写上下文话术）**：提示词中禁止写“承接上一镜”。上个分镜尾帧必须与下个首帧物理状态严密咬合，依靠实体复述来对接环境。

### 三、运镜与转场准则 (Camera & Transitions)
1. **转场手法强制**：必须将上游过渡说明（遮挡物、相似图形等）真实地落实为 Camera Composition 或光影明暗演进。禁仅依赖单一手段。
2. **特殊场景**：跨场景闪回/蒙太奇必须利用遮挡滑越、光影频闪等物理手法过渡。
3. **推拉摇移硬约束 (Camera Moves)**：每场戏至少应用1个高级运镜。OTS (过肩镜头) 必须强制指出 Left-Shoulder OTS 或 Right-Shoulder OTS。不可越轴。
'''

with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'r', encoding='utf-8') as f:
    text=f.read()
m=re.search(r'(## 核心目标.*?)(?=### 四、)', text, re.DOTALL)
if m:
    with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'w', encoding='utf-8') as f:
        f.write(text[:m.start()] + new_text + text[m.end():])
    print('Applied sec 1-3')
else:
    print('Not found')
