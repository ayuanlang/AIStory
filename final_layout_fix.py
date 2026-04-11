import sys

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
import subprocess
subprocess.run(['git', 'checkout', file_path])

with open(file_path, 'r', encoding='utf-8') as f: text = f.read()

def reformat_block(text, button_ident):
    btn_idx = text.find(button_ident)
    if btn_idx == -1: return text

    # The PromptMentionTextarea comes after the button
    prompt_start = text.find('<PromptMentionTextarea', btn_idx)
    prompt_end = text.find('/>', prompt_start) + 2
    prompt_str = text[prompt_start:prompt_end]
    
    # The ReferenceManager comes after the prompt
    ref_start = text.find('<ReferenceManager', prompt_end)
    ref_end = text.find('/>', ref_start) + 2
    ref_str = text[ref_start:ref_end]
    
    # Header starts at 'flex min-h-[52px]'
    header_idx = text.rfind('<div className="flex min-h-[52px]', 0, prompt_start)
    media_and_header = text[header_idx:prompt_start]
    
    # Find the outer container <div className="space-y-2">
    container_start = text.rfind('<div className="space-y-2">', 0, header_idx)
    
    # The end of the block is the closing </div> of the ReferenceManager's wrapper
    # Its wrapper is <div>\n<ReferenceManager ... />\n</div>
    ref_div_start = text.rfind('<div>', prompt_end, ref_start)
    ref_div_end = text.find('</div>', ref_end) + 6
    
    if any(x == -1 for x in [prompt_start, ref_start, header_idx, container_start, ref_div_start, ref_div_end]):
        print(f"Failed to match block for {button_ident}")
        return text
    
    ref_str_upd = ref_str.replace("/>", f" isPortrait={{isPortrait}}\n                                        />")
    
    new_chunk = f"""<div className="space-y-2">
                                        <div className={{isPortrait ? "flex flex-row gap-2 items-start h-[260px]" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full space-y-2" : "w-full space-y-2"}}>
                                                {media_and_header}
                                            </div>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full overflow-hidden" : "w-full hidden"}}>
                                                {ref_str_upd}
                                            </div>
                                        </div>
                                        <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                            {ref_str_upd}
                                        </div>
                                        <div className="mt-2 w-full">
                                            {prompt_str}
                                        </div>
                                    </div>"""
                                    
    return text[:container_start] + new_chunk + text[ref_div_end:]

text = reformat_block(text, "openAssetDetailModal('start')")
text = reformat_block(text, "openAssetDetailModal('end')")
text = reformat_block(text, "openAssetDetailModal('video')") # wait, for video the button is 'keyframe'

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

# Also apply the parseAspectRatio string changes
p1_old = '''             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio);
                    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;
                    const mediaAspectStyle = isPortrait ? { aspectRatio: `${aspectParts.widthPart}/${aspectParts.heightPart}` } : undefined;
                    return (
                    <motion.div'''
p1_new = '''             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || "16:9";
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio) || { widthPart: 16, heightPart: 9 };
                    const isPortrait = aspectParts.heightPart > aspectParts.widthPart;
                    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined;
                    return (
                    <motion.div'''
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace(p1_old, p1_new)
text = text.replace("""const aspectParts = parseAspectRatioParts(preferredAspectRatio);
                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];
                    const mediaAspectStyle = isPortrait ? { aspectRatio: `${aspectParts[0]}/${aspectParts[1]}` } : undefined;""",
                    "const aspectParts = parseAspectRatioParts(preferredAspectRatio) || { widthPart: 16, heightPart: 9 };\n                    const isPortrait = aspectParts.heightPart > aspectParts.widthPart;\n                    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + '/' + aspectParts.heightPart } : undefined;")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied layout reformat!")
