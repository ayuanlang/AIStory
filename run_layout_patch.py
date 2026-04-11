import sys

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

def process_block(text, search_marker):
    idx = text.find(search_marker)
    if idx == -1: return text
    
    # 1. `inner className="space-y-2"`
    outer = text.rfind('className="space-y-2"', 0, idx)
    outer = text.rfind('<div', 0, outer)
    
    inner = text.find('<div className="space-y-2">', outer + 1)
    
    # 2. `Prompt`
    prompt = text.find('<PromptMentionTextarea', inner)
    prompt_close = text.find('/>', prompt) + 2
    prompt_content = text[prompt:prompt_close]
    
    # 3. Media Section
    media_content = text[inner + len('<div className="space-y-2">') : prompt].strip()
    
    # 4. Ref Section 
    inner_close = text.find('</div>', prompt_close) + 6
    ref_div = text.find('<div>', inner_close)
    ref_start = text.find('<ReferenceManager', ref_div)
    ref_close = text.find('/>', ref_start) + 2
    
    ref_content = text[ref_start:ref_close]
    ref_div_close = text.find('</div>', ref_close) + 6
    
    # Replace!
    new_html = f"""<div className={{isPortrait ? "flex flex-row gap-2 h-[260px] items-stretch overflow-hidden" : "space-y-2"}}>
                                        <div className={{isPortrait ? "w-[50%] shrink-0 flex flex-col gap-2 overflow-hidden h-full" : "w-full space-y-2"}}>
                                            {media_content}
                                        </div>
                                        <div className={{isPortrait ? "w-[50%] shrink-0 flex flex-col overflow-hidden h-full" : "w-full hidden"}}>
                                            {ref_content.replace('/>', ' isPortrait={isPortrait}\n                                            />')}
                                        </div>
                                    </div>
                                    <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                        {ref_content}
                                    </div>
                                    <div className="w-full mt-2">
                                        {prompt_content}
                                    </div>"""
                                    
    return text[:inner] + new_html + text[ref_div_close:]

t1 = text
t1 = process_block(t1, "openAssetDetailModal('start')")
t1 = process_block(t1, "openAssetDetailModal('end')")
t1 = process_block(t1, "openAssetDetailModal('keyframe', idx)")

# Now, we also need to make sure ReferenceManager accepts `isPortrait`
# Wait, I am just passing it, it shouldn't crash if it doesn't take it, but let's be sure.

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(t1)

print('Updated ShotsView.jsx blocks!')
