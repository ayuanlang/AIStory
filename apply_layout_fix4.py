import sys

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# We look for "onClick={() => openAssetDetailModal('start')}>"
# then we move up to the container div <div className="space-y-2"> that wraps it.
# Then we move down to <PromptMentionTextarea, grab it, and then to <ReferenceManager, grab it.
# And reassemble.
import re

def process_block(text, button_ident, ref_mgr_ident):
    # Find the prompt mention textarea
    prompt_start = text.find(f'<PromptMentionTextarea', text.find(button_ident))
    if prompt_start == -1: return text
    
    prompt_end = text.find('/>', prompt_start) + 2
    prompt_str = text[prompt_start:prompt_end]
    
    # Find the reference manager
    ref_start = text.find(f'<ReferenceManager', prompt_end)
    if ref_start == -1: return text
    
    ref_end = text.find('/>', ref_start) + 2
    ref_str = text[ref_start:ref_end]
    
    # We also need to locate the </div> the prompt is inside, but wait, 
    # it's simpler to do string replacements on the known parts.
    
    # We want to pull the prompt out, pull the ref mgr out, and rewrite the container around them.
    # The current DOM structure:
    # <div className="space-y-2">
    #     <!-- header and image container -->
    #     <div className="flex min-h-[52px] ...</div>
    #     <div style={mediaAspectStyle} className={`bg-black...` ...</div>
    # 
    #     <PromptMentionTextarea ... />
    # </div>
    # <div>
    #     <ReferenceManager ... />
    # </div>
    
    # Let's find the header start
    # The header starts with <div className="space-y-2"> right above the <div className="flex min-h-[52px]".
    # Let's find the exact text of the PromptMentionTextarea.
    
    # To be extremely safe:
    # 1. Extract the text from <div className="flex min-h-[52px]" to just before <PromptMentionTextarea
    header_idx = text.rfind('<div className="flex min-h-[52px]', 0, prompt_start)
    media_and_header = text[header_idx:prompt_start].strip()
    
    # Now find the outer container of the header
    container_start = text.rfind('<div className="space-y-2">', 0, header_idx)
    
    # Now find the ReferenceManager div
    ref_div_start = text.rfind('<div>', prompt_end, ref_start)
    ref_div_end = text.find('</div>', ref_end) + 6
    
    prompt_div_end = text.find('</div>', prompt_end) + 6
    
    if container_start == -1 or header_idx == -1 or ref_div_start == -1 or ref_div_end == -1:
        print("Couldn't strictly match the blocks")
        return text
    
    # Reassemble:
    # The chunk to replace is from container_start to ref_div_end
    
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
                                        <div className="mt-2">
                                            {prompt_str}
                                        </div>
                                    </div>"""
                                    
    # It replaces exactly from container_start to ref_div_end
    return text[:container_start] + new_chunk + text[ref_div_end:]

text = process_block(text, "openAssetDetailModal('start')", "refs_image_urls")
text = process_block(text, "openAssetDetailModal('end')", "end_ref_image_urls")
text = process_block(text, "openAssetDetailModal('keyframe', idx)", "video_ref_image_urls")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Finished rewriting Blocks!")
