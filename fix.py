import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('className={isPortrait ? "flex flex-col xl:flex-row gap-4" : "space-y-2"}', 'className="space-y-2"')
text = text.replace('className={isPortrait ? "w-full xl:w-[45%] space-y-2" : "space-y-2"}', 'className="space-y-2"')
text = text.replace('<div className={isPortrait ? "w-full xl:w-[55%]" : ""}>', '<div>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Replaced inline conditionals')
