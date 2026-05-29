import re

new_text = '''### 六、实体空间结构描述规则与参考 (Staging & Spatial)
1. **单画布完整性法则**：严防拼贴图，多角色必须有物理统一透视地平面。无横行纸板排布，建立前(FG)、中(MG)、后景(BG)纵深，动作镜切为单镜单人主拍，禁全局大乱斗。
2. **绝对与相对平面占位**：明确位置（left third/center/right third）。明确相对机位的面部朝向（Facing lens/Profile/Back to lens）。
3. **环境锚点定桩 (强制)**：角色的落位、朝向与动作，必须先锚定环境实体（如门、桌子）。正反打镜头必须重建变体锚点坐标体系。
4. **画中画/手机视角法则**：视同双人对打调度。切互打视角时强制重建反向空间背景，不得双面共享相同大景。
5. **构图留白 (Lead/Looking Room)**：角色面对某方或向某方位移，其视线/运动前方必须留出空间余量，禁止紧贴边框避锁。

### 七、视频提示词要求 (Video Content Prompting)
视频需使用自然语言并维持双语，包含五大维度：
1. **`[Global Style]` (全局动态风格)**：重申项目总视觉基调（如 cinematic, 2D 等），此维度严禁越界（禁止恐怖片用明媚光）。
2. **`[Chronological Camera & Action]` (运镜与动作流)**：分段(P1, P2...)描写并融合：
   - **动作逐主体书写模板**：按“环境锚点与机位 -> 角色 -> 关键道具 -> 背景人物 -> 动作结果回填”顺序结构化交代。必须先写落位起势后发力。
   - **微表情与特效过程链**：微表情需拆分“起->中段->落点”，特效需表明“源头->扩散->命中->相位维持”，确保对应时长精准核算。
   - **双缝衔接 (强制)**：P1 必须明写由上镜某元素切转接续（或申首镜）；终段Px必须留下明确的可承接动作结景或视线定格移交下镜。完成 `Start+Video=End` 验证。
   - **群演动态锚定**：若上游输入了群演，落位须挂载特定环境区，附带非木偶态的微动态（如散步/倾听），不得虚空加人。
   - **混光与真颜保护**：复杂冷暖光/霓虹/屏幕复合光下，主铺光要有序。强制要求皮肤高光自然滚降、阴影保留细节，不糊不死白。
3. **`[Dynamic Atmosphere]` (动态光影/焦点)**：跟随阶段说明景深和明暗及焦点流转。
4. **`[Lighting & Tone Resonance with Character Arc]` (光线连动弧光 - 强制)**：固定句式：“该分镜通过 [光源及色温对比参数] 强化了角色在 [情绪阶段] 中的 [感受]”。参数须在基调内映射主角心理起落。
5. **`[Text Rendering]` (物理文字生成)**：仅若上游需要字案时使用，按：「文本」+「时机、位置、入场方式」+「外形」。

'''

with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'(### 六、.*?)(?=### 八、)', text, re.DOTALL)
if m:
    with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'w', encoding='utf-8') as f:
        f.write(text[:m.start()] + new_text + text[m.end():])
    print('Applied sec 6-7')
else:
    print('Pattern not found')
