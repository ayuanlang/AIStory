import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure we add isPortrait={isPortrait} safely.
text = text.replace("title={t('参考图（起始帧）', 'Refs (Start)')}", "title={t('参考图（起始帧）', 'Refs (Start)')} isPortrait={isPortrait}")
text = text.replace("title={t('参考图（结束帧）', 'Refs (End)')}", "title={t('参考图（结束帧）', 'Refs (End)')} isPortrait={isPortrait}")
text = text.replace("title={t('参考图（实体）', 'Refs (Entity)')}", "title={t('参考图（实体）', 'Refs (Entity)')} isPortrait={isPortrait}")

# Find PromptMentionTextarea blocks
def repl_block(m):
    media_div = m.group(1)
    prompt_chunk = m.group(2)
    ref_manager_chunk = m.group(3)
    
    return f'''
                                        <div className={{isPortrait ? "flex flex-row gap-2 h-[260px]" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full" : "w-full"}}>
                                                {media_div}
                                            </div>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full" : "w-full hidden"}}>
                                                {ref_manager_chunk}
                                            </div>
                                        </div>
                                        <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                            {ref_manager_chunk}
                                        </div>
                                        {prompt_chunk}
                                        </div>
                                        <div>
    '''

# We need to capture: 1) The media div 2) The textarea 3) the ReferenceManager
# The structure is:
# <div style={mediaAspectStyle} ... > ... </div>
# <PromptMentionTextarea ... />
# </div>
# <div>
# <ReferenceManager ... />
# </div>

pattern = re.compile(
    r'(<div style=\{mediaAspectStyle\} className=\{`bg-black rounded border relative group overflow-hidden.*?</div>)\s*'
    r'(<PromptMentionTextarea.*?</PromptMentionTextarea>)\s*'
    r'</div>\s*'
    r'<div>\s*'
    r'(<ReferenceManager[^>]*?(?:/>|>.*?</ReferenceManager>))\s*'
    r'</div>',
    re.DOTALL
)

new_text = pattern.sub(repl_block, text)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_text)

print(f"Replaced {len(pattern.findall(text))} occurrences")