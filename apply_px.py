import re

def main():
    with open('backend/app/core/prompts/skills/shot_generation.md', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Fix Camera Movement Px
    old_c = r'(  2\. \*\*`\[Camera Movement\]`[^\n]*：\n)(     - \*\*按动作段落\(Px\)拆解运镜\*\*：必须与下文 `\[Action Beat Chain\]` 的动作段落 \(P1\), \(P2\) 等严密对应。分别写出在 \(P1\) 动作时镜头如何配合运镜，在 \(P2\) 动作时镜? ?头如何跟进或转折。)'

    new_c = r'\g<1>     - **Px (Phase) 动作段落定义**：Px 代表该分镜内基于时间线推移的“连贯动作阶段”（Phase 1, Phase 2, Phase 3...）。每个 Px 代表一个不可忽略的动作转折、视听节拍（Beat）或情绪演进。段落的数量（Px）应根据镜头设定偏好（长/短镜头）、预估时长以及人物动作与剧情表达的复杂程度综合决定，并不局限于两个。\n     - **按动作段落(Px)拆解运镜**：必须与下文 `[Action Beat Chain]` 的动作段落 (P1), (P2), (P3) 等严密对应。分别写出在 (P1) 动作时镜头如何配合运镜，在 (Px) 动作阶段镜头如何跟进或转折。绝不要把运镜和动作分开写。'

    text = re.sub(old_c, new_c, text)

    # 2. Fix Action Beat Chain
    old_a = r'     - \*\*动作时序切割\*\*：将本镜内容依据时间线严格划分为 \(P1\) \(P2\) 等主节拍顺序推进。'
    new_a = r'     - **动作时序切割**：将本镜内容依据时间线严格划分为 (P1), (P2), (P3) 等主节拍顺序推进。'

    text = re.sub(old_a, new_a, text)

    with open('backend/app/core/prompts/skills/shot_generation.md', 'w', encoding='utf-8') as f:
        f.write(text)

    print('Patched Px Phase correctly!')

if __name__ == '__main__':
    main()
