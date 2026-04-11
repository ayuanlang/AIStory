import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Inject isPortrait
is_portrait_def = """    const functionApiConfigs = useFunctionApis();
    const aspectParts = parseAspectRatioParts(project?.aspect_ratio || '16:9');
    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;"""
text = text.replace("    const functionApiConfigs = useFunctionApis();", is_portrait_def)

# 2. Replace aspect-video with ternary condition
# There are 5 places. Let's do them one by one based on surrounding code.

# A)
text = text.replace(
    'className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden"',
    'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden`}'
)

# B) & C) There are 2 of these
text = text.replace(
    'className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center ${',
    'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center ${'
)

# D)
text = text.replace(
    'className="aspect-video bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center"',
    'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center`}'
)

# E)
text = text.replace(
    'className="aspect-video bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer"',
    'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer`}'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Replaced aspect ratios for ShotsView properly without layout corruptions.")
