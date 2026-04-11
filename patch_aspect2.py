import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace conditionally in ALL template literals safely via regex:
text = re.sub(r'className={`aspect-video\s+', r'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} ', text)
text = re.sub(r'className="aspect-video\s+', r'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} ', text)
text = re.sub(r'className=\'aspect-video\s+', r'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} ', text)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Complete regex replacement of aspect-video")
