import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure isPortrait is passed to ReferenceManager
text = text.replace('uiLang={uiLang}\n                                            onPickMedia={openMediaPicker}\n                                            storageKey="ref_image_urls"\n                                            strictPromptOnly={true}\n                                        />',
                    'uiLang={uiLang}\n                                            onPickMedia={openMediaPicker}\n                                            storageKey="ref_image_urls"\n                                            strictPromptOnly={true}\n                                            isPortrait={isPortrait}\n                                        />')
text = text.replace('uiLang={uiLang}\n                                            onPickMedia={openMediaPicker}\n                                            storageKey="end_ref_image_urls"\n                                            strictPromptOnly={true}\n                                        />',
                    'uiLang={uiLang}\n                                            onPickMedia={openMediaPicker}\n                                            storageKey="end_ref_image_urls"\n                                            strictPromptOnly={true}\n                                            isPortrait={isPortrait}\n                                        />')
text = text.replace('uiLang={uiLang}\n                                            onPickMedia={openMediaPicker}\n                                            storageKey="video_ref_image_urls"\n                                            strictPromptOnly={resolveVideoModeFromTech(tech) !== \'entity_refs\'}\n                                        />',
                    'uiLang={uiLang}\n                                            onPickMedia={openMediaPicker}\n                                            storageKey="video_ref_image_urls"\n                                            strictPromptOnly={resolveVideoModeFromTech(tech) !== \'entity_refs\'}\n                                            isPortrait={isPortrait}\n                                        />')

text = text.replace('strictPromptOnly={resolveVideoModeFromTech(tech) !== \'entity_refs\'}', 'strictPromptOnly={resolveVideoModeFromTech(tech) !== \'entity_refs\'}\n                                            isPortrait={isPortrait}')

# 1. Start Frame
start_block_regex = r'(<div style=\{mediaAspectStyle\} className=\{`bg-black rounded border relative group overflow-hidden(.*?)</div>)(\s*<PromptMentionTextarea.*?</PromptMentionTextarea>\s*</div>\s*<div>\s*<ReferenceManager.*?</ReferenceManager>\s*</div>)'

def start_repl(m):
    media = m.group(1)
    rest = m.group(3)
    # Split out the prompt textarea and the reference manager
    prompt_match = re.search(r'(<PromptMentionTextarea.*?</PromptMentionTextarea>)', rest, re.DOTALL)
    ref_match = re.search(r'(<ReferenceManager.*?</ReferenceManager>)', rest, re.DOTALL)
    if not prompt_match or not ref_match: return m.group(0)
    
    return f'''<div className={{isPortrait ? "flex flex-row gap-2" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[60%] shrink-0" : "w-full"}}>
                                                {media}
                                            </div>
                                            <div className={{isPortrait ? "w-[40%] shrink-0" : "w-full hidden"}}>
                                                {ref_match.group(1)}
                                            </div>
                                        </div>
                                        <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                            {ref_match.group(1)}
                                        </div>
                                        {prompt_match.group(1)}
                                        </div>
                                        <div>'''

text = re.sub(start_block_regex, start_repl, text, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied layout modifications!")
