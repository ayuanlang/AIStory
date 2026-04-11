import sys

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

def side_by_side(text, keyword, ref_title):
    # Find keyword (e.g., 'start') to locate the block
    btn_str = f"onClick={{() => openAssetDetailModal('{keyword}')}}"
    block_idx = text.find(btn_str)
    if block_idx == -1:
        # try alternative
        btn_str = f"onClick={{() => openAssetDetailModal('{keyword}', idx)}}"
        block_idx = text.find(btn_str)
        if block_idx == -1:
            return text

    # Header starts at `flex min-h-[52px]`
    header_idx = text.rfind('<div className="flex min-h-[52px]', 0, block_idx)
    
    # Outer container
    container_start = text.rfind('<div className="space-y-2">', 0, header_idx)
    
    # Prompt bounds
    prompt_start = text.find('<PromptMentionTextarea', block_idx)
    prompt_end = text.find('/>', prompt_start) + 2
    prompt_str = text[prompt_start:prompt_end]
    
    # Ref manager bounds
    ref_start = text.find('<ReferenceManager', prompt_end)
    ref_end = text.find('/>', ref_start) + 2
    ref_str = text[ref_start:ref_end]
    
    # Image container bounds. Starts at header_idx
    # Ends right before prompt_start
    image_and_header = text[header_idx:prompt_start].strip()
    # Actually, there's a `</div>` right before prompt_start that closes the `space-y-2`?
    # No, wait, they are all inside the same space-y-2 currently.
    # The structure:
    # <div className="space-y-2"> [container_start]
    #   <div className="space-y-2">                     <-- Wait, there's an extra space-y-2?
    #     <div className="flex min-h-[52px] ...</div>   [header_idx]
    #     <div style={mediaAspectStyle} > ... </div>
    #     <PromptMentionTextarea ... />                 [prompt_start]
    #   </div>
    #   <div>
    #     <ReferenceManager />
    #   </div>
    
    # Wait, the extra `space-y-2` comes from fix.py !
    # let's find the closing of ref_div
    ref_div_end = text.find('</div>', ref_end) + 6
    
    # modify ref_str to include isPortrait
    ref_str = ref_str.replace("/>", " isPortrait={isPortrait}\n                                        />")
    
    new_chunk = f"""<div className="space-y-2">
                                        <div className={{isPortrait ? "flex flex-row gap-2 items-start h-[280px]" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full flex flex-col gap-2 overflow-hidden" : "w-full space-y-2"}}>
                                                {image_and_header.replace('</div>\\n                                        <PromptMentionTextarea', '')}
                                            </div>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full flex flex-col overflow-hidden" : "w-full hidden"}}>
                                                {ref_str}
                                            </div>
                                        </div>
                                        <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                                {ref_str}
                                        </div>
                                        <div className="mt-2 w-full">
                                                {prompt_str}
                                        </div>
    """
    
    return text[:container_start] + new_chunk + text[ref_div_end:]

text = side_by_side(text, "start", "refs_image_urls")
text = side_by_side(text, "end", "end_ref_image_urls")
text = side_by_side(text, "keyframe", "video_ref_image_urls")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied final side-by-side ref structure!")
