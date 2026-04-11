import sys
with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center"',
    'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center`}'
)

with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
