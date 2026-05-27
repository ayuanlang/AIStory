import re

with open('backend/app/core/prompts/script_generator_episode_script.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove Dimension Completeness Gate and Camera rules
text = re.sub(r'- Natural-Prose Camera Rule.*?(- Panel-Language Restraint)', r'\1', text, flags=re.DOTALL)
text = re.sub(r'- Dimension Completeness Gate.*?(- Hierarchical continuity contract)', r'\1', text, flags=re.DOTALL)

beats_section = '''- Scene/Beat supplement (Mandatory script writing rules):
  - **{Beats} (节拍流)**：按时间顺序排列的动作与对白单元。
    - **服装一致性约束 (Wardrobe Consistency)**：由于角色资产已预生成，Beats 中禁止出现穿衣/脱衣/换装/试衣/更衣及其同义动作；需要表达推进时，改用表情、手部动作、道具互动替代。
    - **强聚焦剧情构建**：集中于**情节、动作、对白、表情、交互**的生动描写。先**不进行分镜/机位/镜头的考虑**。
    - **细致的微表情与动作**：动作应具备逻辑连贯性，对白必须与角色的动作、微表情、呼吸、停顿紧密结合。
    - **主体关系明确**：每个 Beat 必须明确角色之间的相对关系（例如：接近、后退、对视、避开视线、身体接触等）。
    - **状态过渡自然**：凡位置/朝向/视线/接触任一项发生变化，必须自然描述从旧状态到新状态的过渡过程，禁止只给结果态。
    - **剧本到 Beats 生成要求 (Script-to-Beats Generation Mandate)**：
      1) **顺序一致**：Beats 的顺序必须严格跟随原始剧本事件顺序，禁止打乱因果先后。
      2) **逐项覆盖**：每一项信息（动作、台词、情绪反应）必须落到至少一个 Beat。
      3) **动作闭环**：每个动作必须明确 执行者 -> 受体/对象 -> 可见结果状态。
      4) **补桥接动作**：若剧本文本存在物理空间跳跃，必须补写过渡过程（如移步、转身），不可生硬跳跃。
      5) **禁抽象替代**：禁止使用气氛紧张了/关系恶化了总结替代可视动作，必须改写为具体的表情和互动。
      6) **实体引用**：Beat 描述中涉及的所有**角色**、**道具**、**环境**均须用 [] 包裹（例如：CHAR:[@Alice] 走到 ENV:[窗边] 拿起 PROP:[水杯]）。角色名必须加 @，环境与道具不加 @。
      7) **稳定状态**：Beat 的起点和终点必须是相对稳定的物理状态（便于后续生成帧）。
'''

text = re.sub(r'- Scene/Beat supplement.*?Output format \(Markdown\):', beats_section + '\nOutput format (Markdown):\n', text, flags=re.DOTALL)

output_format = '''Output format (Markdown):
# {episode_number}-{episode_title}

## -1) 类型研判与参考执行（必须先写）
- Primary Type（主类型）: ...
- Secondary Type（可选）: ...
- Benchmark Pattern Set（抽象参考模式）:
  - Hollywood / International Narrative Pattern: ...
- Script Execution Rules（本集脚本执行规则）: ...

## Logline
- (1-2 sentences)

## Scenes
For each scene, use:
### Scene {i} {scene_id=EPxx_SCyy}: {scene_name}（{location} / {time}）
- Entry State: ...
- Exit State: ...
- 目标/冲突/赌注：...
- 节拍（按时序；按人物驱动；对白与动作情绪一体化）：
  1) 【角色名】（语气/情绪/状态）：动作/表情/走位/与道具互动……同时说：台词……。（必要时补一行对方可见反应）
  2) 【角色名】（语气/情绪/状态）：动作……说：台词……。
  3) ……
-配乐与音效：

写作要求（适用于每个节拍）：
- 每个节拍都必须明确谁在做什么，怎么说，并保证先后因果清晰。
- 聚焦于**情节推进、人物动作、精细对白、微表情、角色间交互**。
- **不要**在节拍中描写摄影机机位、镜头参数或景别。用文学剧本的自然描写来刻画剧本。
- 台词不要孤立成清单；必须嵌在同一个节拍里，与动作/微表情/停顿/视线绑定。
- 需要舞台调度时，把走位写在该人物的节拍里（例如：靠近/后退/绕过/挡住视线）。
- 节拍短而连贯：用具体可见行为推动信息增量与情绪转折。

## Ending Hook
- (1-2 sentences, cliffhanger or next-episode hook)
'''

text = re.sub(r'Output format \(Markdown\):.*', output_format, text, flags=re.DOTALL)

with open('backend/app/core/prompts/script_generator_episode_script.txt', 'w', encoding='utf-8') as f:
    f.write(text)

with open('backend/app/core/prompts/promo_generator_episode_script.txt', 'w', encoding='utf-8') as f:
    f.write(text)

print(done)

