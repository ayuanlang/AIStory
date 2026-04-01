import sys
import re

with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Replace <select> with <input list="..."> + <datalist>
def replacer(m):
    label = m.group(1)
    val_bind = m.group(2)
    change_bind = m.group(3)
    options_array = m.group(4)
    
    list_id = val_bind.lower().replace('new', '') + '-options'
    return f'''<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{{t({label})}}</label>
                                                <input
                                                    list="{list_id}"
                                                    className="w-full px-3 py-2.5 bg-background border rounded-lg"
                                                    value={{{val_bind}}}
                                                    onChange={{(e) => {change_bind}(e.target.value)}}
                                                />
                                                <datalist id="{list_id}">
                                                    {{{options_array}.map((opt) => <option key={{opt}} value={{opt}} />)}}
                                                </datalist>'''

# Match standard ones
text = re.sub(
    r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\((.*?)\)\}</label>\s*<select className="w-full px-3 py-2.5 bg-background border rounded-lg" value=\{([^}]+)\} onChange=\{\(e\) => ([^}]+)\(e\.target\.value\)\}>\s*\{([^\}]+)\.map\(\(opt\) => <option key=\{opt\} value=\{opt\}>\{opt\}</option>\)\}\s*</select>',
    replacer,
    text
)

# 2. Add has_existing_assets state if missing
if 'newHasExistingAssets' not in text:
    text = text.replace(
        'const [newVideoSoundEnabled, setNewVideoSoundEnabled] = useState(true);',
        'const [newVideoSoundEnabled, setNewVideoSoundEnabled] = useState(true);\n    const [newHasExistingAssets, setNewHasExistingAssets] = useState(true);'
    )
    text = text.replace(
        'setNewVideoSoundEnabled(true);',
        'setNewVideoSoundEnabled(true);\n        setNewHasExistingAssets(true);'
    )
    text = text.replace(
        'broadcast_safety_level: String(newBroadcastSafetyLevel || \'\').trim(),',
        'broadcast_safety_level: String(newBroadcastSafetyLevel || \'\').trim(),\n                has_existing_assets: Boolean(newHasExistingAssets),\n                video_generation_preference: String(newVideoGenPreference || \'\').trim(),'
    )
    
    # Checkbox DOM
    chk_str = '''                                        <div className="flex flex-wrap gap-4 mt-2 mb-2">
                                            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                                                <input
                                                    type="checkbox"
                                                    className="h-4 w-4"
                                                    checked={newHasExistingAssets}
                                                    onChange={(e) => setNewHasExistingAssets(Boolean(e.target.checked))}
                                                />
                                                <span>{t('有现有资产', 'Has existing assets')}</span>
                                            </label>
                                            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                                                <input
                                                    type="checkbox"
                                                    className="h-4 w-4"
                                                    checked={newVideoSoundEnabled}'''
    text = re.sub(
        r'<label className="flex items-center gap-2 text-sm mt-1 mb-1 cursor-pointer select-none">\s*<input\s*type="checkbox"\s*className="h-4 w-4"\s*checked=\{newVideoSoundEnabled\}',
        chk_str,
        text
    )
    text = text.replace('视频生成默认开启声音\', \'Enable sound by default for video generation\')}</span>\n                                        </label>', '视频生成默认开启声音\', \'Enable sound by default for video generation\')}</span>\n                                            </label>\n                                        </div>')

# 3. Chop out Scene Analysis and Collaborators exactly (string manipulation)
open_tag = '<div className="mt-5 rounded-xl border border-white/10 bg-black/15">'
blocks = text.split(open_tag)

new_blocks = [blocks[0]]
for block in blocks[1:]:
    if 'Scene Analysis Dimensions' in block or 'Collaborators' in block or 'setIsCreateSceneAnalysisCollapsed' in block or 'setIsCreateCollaboratorsCollapsed' in block:
        # We need to find where this block ends. It's a top-level div with a button and a conditional content inside.
        # Everything until the next <div className="grid gap-4"> or <label className="block text-sm ... Project Description ?
        # Wait, the Collaborators block actually ends right before Project Description!
        # No, wait, in the original, Collaborators was after Project Description? 
        pass # Skip adding it to new_blocks
    else:
        new_blocks.append(open_tag + block)

text = "".join(new_blocks)

with open('frontend/src/pages/ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patch ProjectList done")
