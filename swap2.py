import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f: text = f.read()

def swap_blocks(t, marker, label):
    match_idx = t.find(marker)
    if match_idx == -1: return t

    block_start = t.rfind('<div className="flex min-h-[52px]', 0, match_idx)
    prompt_start = t.find('<PromptMentionTextarea', block_start)
    ref_start = t.find('<ReferenceManager', prompt_start)
    ref_end = t.find('/>', ref_start) + 2
    prompt_end = t.find('/>', prompt_start) + 2
    
    media_chunk = t[block_start:prompt_start].strip()
    # DO NOT strip </div> here, they are siblings!
    
    prompt_chunk = t[prompt_start:prompt_end]
    ref_chunk = t[ref_start:ref_end]
    
    ref_chunk = ref_chunk.replace('/>', f' isPortrait={{isPortrait}}\n                                        />')
    
    cont_start = t.rfind('<div className="space-y-2">', 0, block_start)
    
    ref_div_end = t.find('</div>', ref_end) + 6
    
    new_html = f"""<div className="space-y-2">
                                        <div className={{isPortrait ? "flex flex-row gap-2 h-[260px] items-start" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[45%] shrink-0 flex flex-col gap-2 overflow-hidden h-full" : "w-full space-y-2"}}>
                                                {media_chunk}
                                            </div>
                                            <div className={{isPortrait ? "w-[55%] shrink-0 h-full flex flex-col overflow-hidden" : "w-full hidden"}}>
                                                {ref_chunk}
                                            </div>
                                        </div>
                                        <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                            {ref_chunk}
                                        </div>
                                        <div className="w-full mt-2">
                                            {prompt_chunk}
                                        </div>
    """
    
    return t[:cont_start] + new_html + t[ref_div_end:]

text = swap_blocks(text, "openAssetDetailModal('start')", "start")
text = swap_blocks(text, "openAssetDetailModal('end')", "end")
text = swap_blocks(text, "openAssetDetailModal('keyframe')", "video")

# Patch parseAspectRatio
p1_old = '''             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio);
                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];
                    const mediaAspectStyle = isPortrait ? { aspectRatio: f"{aspectParts[0]}/{aspectParts[1]}" } : undefined;
                    return (
                    <motion.div'''
                    
if p1_old in text:
    p1_new = '''             <AnimatePresence>
                    {editingShot && (() => {
                        const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || "16:9";
                        const aspectParts = parseAspectRatioParts(preferredAspectRatio) || { widthPart: 16, heightPart: 9 };
                        const isPortrait = aspectParts.heightPart > aspectParts.widthPart;
                        const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined;
                        return (
                        <motion.div'''
    text = text.replace(p1_old, p1_new)
else:
    # try patching line by line
    text = text.replace("const aspectParts = parseAspectRatioParts(preferredAspectRatio);\n                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];\n                    const mediaAspectStyle = isPortrait ? { aspectRatio: f\"{aspectParts[0]}/{aspectParts[1]}\" } : undefined;", "const aspectParts = parseAspectRatioParts(preferredAspectRatio) || { widthPart: 16, heightPart: 9 };\n                    const isPortrait = aspectParts.heightPart > aspectParts.widthPart;\n                    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + '/' + aspectParts.heightPart } : undefined;")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Reordered layout successfully!")
