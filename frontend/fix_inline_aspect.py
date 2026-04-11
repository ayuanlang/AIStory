import re
with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('${isPortrait ? "aspect-[9/16]" : "aspect-video"}', '${isPortrait ? "" : "aspect-video"}')

t1 = 'className={`${isPortrait ? "" : "aspect-video"} bg-black/60 flex items-center justify-center text-muted-foreground relative'
r1 = 'style={mediaAspectStyle} className={`${isPortrait ? "" : "aspect-video"} bg-black/60 flex items-center justify-center text-muted-foreground relative'
text = text.replace(t1, r1)

t2 = 'className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ?'
r2 = 'style={mediaAspectStyle} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ?'
text = text.replace(t2, r2)

t3 = 'className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ?'
r3 = 'style={mediaAspectStyle} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ?'
text = text.replace(t3, r3)

t4 = 'className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center`}'
r4 = 'style={mediaAspectStyle} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center`}'
text = text.replace(t4, r4)

t5 = 'className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center`}'
r5 = 'style={mediaAspectStyle} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center`}'
text = text.replace(t5, r5)

with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied mediaAspectStyle changes")
