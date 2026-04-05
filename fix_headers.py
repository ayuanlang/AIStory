# -*- coding: utf-8 -*-
with open('c:/AIStory/backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('#### Part 2A — Characters', '#### Part 2A — Characters （对应最终 JSON 对象的 "characters" 数组）')
text = text.replace('#### Part 2B — Props', '#### Part 2B — Props （对应最终 JSON 对象的 "props" 数组）')
text = text.replace('#### Part 2C — Environments', '#### Part 2C — Environments （对应最终 JSON 对象的 "environments" 数组）')
text = text.replace('#### Part 2D — Project Visual Backfill JSON (Mandatory)', '#### Part 2D — Project Visual Backfill （对应最终 JSON 对象的 "project_visual_backfill" 对象）')

with open('c:/AIStory/backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed headers!')
