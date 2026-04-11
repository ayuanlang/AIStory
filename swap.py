import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f: text = f.read()

def swap_blocks(t, marker):
    match_idx = t.find(marker)
    if match_idx == -1: return t

    block_start = t.rfind('<div className="flex min-h-[52px]', 0, match_idx)
    prompt_start = t.find('<PromptMentionTextarea', block_start)
    ref_start = t.find('<ReferenceManager', prompt_start)
    ref_end = t.find('/>', ref_start) + 2
    prompt_end = t.find('/>', prompt_start) + 2
    
    media_chunk = t[block_start:prompt_start].strip()
    if media_chunk.endswith('</div>'): media_chunk = media_chunk[:-6].strip()
    
    prompt_chunk = t[prompt_start:prompt_end]
    ref_chunk = t[ref_start:ref_end]
    
    # insert isPortrait inside the ref_chunk safely
    ref_chunk = ref_chunk.replace('/>', ' isPortrait={isPortrait}\n                                        />')
    
    cont_start = t.rfind('<div className="space-y-2">', 0, block_start)
    
    # We find the </div> ending the ReferenceManager wrapper div
    ref_div_end = t.find('</div>', ref_end) + 6
    
    new_html = f"""<div className="space-y-2">
                                        <div className={{isPortrait ? "flex flex-row gap-2 h-[260px] items-start" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[45%] shrink-0 flex flex-col gap-2 overflow-hidden" : "w-full space-y-2"}}>
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
                                        </div>"""
    
    return t[:cont_start] + new_html + t[ref_div_end:]

text = swap_blocks(text, "openAssetDetailModal('start')")
text = swap_blocks(text, "openAssetDetailModal('end')")
text = swap_blocks(text, "openAssetDetailModal('keyframe')")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Reordered layout successfully!")
