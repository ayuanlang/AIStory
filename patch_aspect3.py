import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# isPortrait definition
is_portrait_def = """    const functionApiConfigs = useFunctionApis();
    const aspectParts = parseAspectRatioParts(project?.aspect_ratio || '16:9');
    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;"""
text = text.replace("    const functionApiConfigs = useFunctionApis();", is_portrait_def)

# Find ALL exact matches and rigorously replace them!

orig = 'className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden"'
repl = 'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden`}'
text = text.replace(orig, repl)

orig = 'className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ? \'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]\' : \'border-white/10\'}`}'
repl = 'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ? \'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]\' : \'border-white/10\'}`}'
text = text.replace(orig, repl)

orig = 'className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ? \'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]\' : \'border-white/10\'}`}'
repl = 'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ? \'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]\' : \'border-white/10\'}`}'
text = text.replace(orig, repl)

orig = 'className="aspect-video bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center"'
repl = 'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center`}'
text = text.replace(orig, repl)

orig = 'className="aspect-video bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center"'
repl = 'className={`${isPortrait ? "aspect-[9/16]" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center`}'
text = text.replace(orig, repl)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Finished strict replacement string")
