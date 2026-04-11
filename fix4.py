import sys
file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

def re_block(text, label, search_tag):
    matches = []
    idx = text.find(search_tag)
    while idx != -1:
        if 'uppercase font-bold' in text[max(0, idx-200):idx]:
            matches.append(idx)
        idx = text.find(search_tag, idx + 1)
        
    print(f"Found {len(matches)} matches for {label}")
    if len(matches) == 0: return text
    
    idx = matches[0] 
    
    outer = text.rfind('className="space-y-2"', 0, idx)
    outer = text.rfind('<div', 0, outer)
    
    inner = text.find('<div className="space-y-2">', outer + 1)
    
    prompt = text.find('<PromptMentionTextarea', inner)
    if prompt == -1: return text
    prompt_close = text.find('/>', prompt) + 2
    prompt_content = text[prompt:prompt_close]
    
    media_content = text[inner + len('<div className="space-y-2">') : prompt].strip()
    
    inner_close = text.find('</div>', prompt_close) + 6
    ref_div = text.find('<div>', inner_close)
    ref_start = text.find('<ReferenceManager', ref_div)
    if ref_start == -1: return text
    ref_close = text.find('/>', ref_start) + 2
    
    ref_content = text[ref_start:ref_close]
    ref_div_close = text.find('</div>', ref_close) + 6
    
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
t1 = re_block(t1, 'start', "t('\u8d77\u59cb\u5e27', 'Start Frame')")
t1 = re_block(t1, 'end', "t('\u5c3e\u5e27', 'End Frame')")
t1 = re_block(t1, 'video', "t('\u89c6\u9891', 'Video')")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(t1)

print('AST cleanly updated again!')
