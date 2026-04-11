import sys

def update_block(content, marker):
    idx = content.find(marker)
    if idx == -1: return content

    # Find the outer container
    outer_start = content.rfind('<div className="space-y-2">', 0, idx)
    
    # Prompt
    prompt_start = content.find('<PromptMentionTextarea', idx)
    prompt_end = content.find('/>', prompt_start) + 2
    prompt_tag = content[prompt_start:prompt_end]

    # Media section ends before Prompt
    media_start = content.find('<div className="space-y-2">', outer_start + 1)
    if media_start == -1 or media_start > prompt_start:
        media_start = outer_start
    media_end = content.rfind('</div>', media_start, prompt_start) + 6
    media_tag = content[media_start + len('<div className="space-y-2">'):media_end].strip()

    # Ref manager
    ref_start = content.find('<ReferenceManager', prompt_end)
    ref_end = content.find('/>', ref_start) + 2
    ref_tag = content[ref_start:ref_end]

    # div closing Ref
    ref_block_end = content.find('</div>', ref_end) + 6

    new_block = f"""<div className="space-y-2">
                            <div className={{isPortrait ? "flex flex-row gap-2 h-[260px] items-stretch overflow-hidden" : "space-y-2"}}>
                                <div className={{isPortrait ? "w-[50%] shrink-0 flex flex-col gap-2 overflow-hidden h-full" : "w-full space-y-2"}}>
                                    {media_tag}
                                </div>
                                <div className={{isPortrait ? "w-[50%] shrink-0 flex flex-col overflow-hidden h-full" : "w-full hidden"}}>
                                    {ref_tag.replace('/>', ' isPortrait={true} />')}
                                </div>
                            </div>
                            <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                {ref_tag}
                            </div>
                            <div className={{isPortrait ? "w-full mt-2" : "w-full"}}>
                                {prompt_tag}
                            </div>
"""
    return content[:outer_start] + new_block + content[ref_block_end:]

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

text = update_block(text, "openAssetDetailModal('start')")
text = update_block(text, "openAssetDetailModal('end')")
text = update_block(text, "openAssetDetailModal('keyframe', idx)")

# Also update the ReferenceManager component itself to take isPortrait from props
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Done')
