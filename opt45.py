import re

new_text = '''### 四、动作规范与物理逻辑 (Action Directing)
1. **单镜结果闭环与动作定格 (强制)**：动作必须写明最终的物理落地或停顿定格效果，绝不悬空切镜。P阶段结尾强制回填新状态。
2. **方向性位移强制“起->终”**：所有位移（跑向、走向、穿越等）必须显式写明起点的环境锚点与终点的环境锚点。
3. **全员动作不留白 (含群演)**：
   - 画内的主配角必须有明确动作或倾听/防备的姿态。
   - **群演与背景人物**：若上游输入了群演，必须交代其在环境锚点（如后景街道、吧台侧边）的群落分布与附带随机生态动作（交谈/走动）。严禁擅自造词补加群演，严禁僵尸木偶式静止。
   - 施力方写出动作，受力方必须写出生理/物理滞后反应（如僵硬、后侧步）。
4. **空间重力与速度量化**：激烈动作交代明确的力度与速率（如“迟缓但沉重以致脚步打滑”），并给出物理相对距离（如“后退半个身位”）。
5. **道具与配件连续**：一旦写明拾取或穿戴道具，其后每个分镜必须交代“仍握持/仍佩戴”，直至明确写出放下。

### 五、对话与表情规范 (Dialogue & Expressions)
1. **对白逐字绝对保留 (强制)**：不仅不能删字，还必须附加完整的极简元数据格式：`(Pn) {说话动作} — Dialogue/OS/V.O. (CHAR:[@Name]) (voice_type: xx, tone: xx, speed: xx, volume: xx): "完整全句" — {听者视觉反应}`。
2. **常规对话清澈布光 (强制)**：除上游明确写的恐怖/剪影外，正常对话的静态和动态提示词中，必须显式指明至少一个具体光源（如窗光/台灯）与照射方向，保护面部与口型微表情可见。
3. **禁止OS旁白张嘴 (OS/V.O. Guard)**：若句子为画外音/旁白，画面无论出谁都强制写明闭口倾听或内心独白状，切勿错位张嘴。
4. **微表情多段生成 (强制拆分)**：任何落泪、心虚、尴尬、怒意等不能只写最终一个词，必须拆分为“前置动作 -> 中段变化 -> 落点结景”（如：先盯住、喉结滚动，再闭眼泪水溢出）。
5. **情绪与道具双特写法则**：关键转折情绪强制配全面特写(`Close-up` / `Extreme Close-up`)。关键线索道具介入强制配 `Insert Shot`。
6. **液态极致真实 (Fluid Realism)**：凡出现汗水、眼泪、血液，必须强制在提示词中附加物理级高逼真光影表现（`photorealistic glistening tears...`）防塑料感。

'''

with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'(### 四、.*?)(?=### 六、)', text, re.DOTALL)
if m:
    with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation_optimized.md', 'w', encoding='utf-8') as f:
        f.write(text[:m.start()] + new_text + text[m.end():])
    print('Applied sec 4-5')
else:
    print('Pattern not found')
