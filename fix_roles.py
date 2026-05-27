# coding: utf-8
import os
path = 'backend/app/core/prompts/master_story_architect.md'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

adapter_rules = '''### 受众定位适配法则（根据男频/女频受众定位极化核心看点与张力）
你需要敏锐捕捉用户输入中的 类型、核心受众等关键词，并自适应采取针对性的编剧策略：
- **男频路线 (Male-Oriented / Power Fantasy)**：
  - **核心看点**：阶层跃升、力量升级、宏大规模、权谋征服、极度打脸与复仇爽感。
  - **冲突结构**：多以绝对的压制开局，通过智武双全破坏阶层。反转多体现在扮猪吃虎与反杀。
  - **人物关系**：更强调阵营对抗、利益交换、兄弟羁绊。
- **女频路线 (Female-Oriented / Emotional Resonance)**：
  - **核心看点**：深度的情感共鸣、极致的虐恋与救赎、相爱相杀、宅斗宫斗、绝境逆袭。
  - **冲突结构**：多以情感背叛、伦理道德困境驱动。高潮往往体现在手撕逆境、情感与权力的双掌控。
  - **人物关系**：人际羁绊是绝对核心。强调拉扯感、宿命感，对微小心理防线被击溃的过程有极高要求。
'''

if '受众定位适配法则' not in text:
    text = text.replace('## 用户的输入说明', adapter_rules + '\n\n---\n\n## 用户的输入说明')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
