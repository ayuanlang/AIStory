import re

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# state
if 'const [createMode, setCreateMode] = useState(' not in text:
    text = text.replace('const [subTab, setSubTab] = useState(\'character\');', 'const [subTab, setSubTab] = useState(\'character\');\n    const [createMode, setCreateMode] = useState(\'manual\');')

# handleCreate: explicitly reset createMode
handle_create = '''const handleCreate = async () => {
        setCreateMode('manual');'''
text = text.replace('const handleCreate = async () => {\n', handle_create + '\n')

# inject tabs UI under the header of the viewingEntity modal
header_end = '<div className="p-6 overflow-y-auto custom-scrollbar flex-1 bg-black/10 flex flex-col gap-6">'

tabs_ui = '''
                            {isNew && (
                                <div className="flex border-b border-white/10 px-6 pt-2 shrink-0 bg-black/20 z-10 relative">
                                    <button
                                        type="button"
                                        onClick={() => setCreateMode('manual')}
                                        className={px-4 py-2 border-b-2 text-sm font-medium transition-colors }
                                    >
                                        {t('文字输入', 'Manual Input')}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setCreateMode('image')}
                                        className={px-4 py-2 border-b-2 text-sm font-medium transition-colors }
                                    >
                                        {t('图片反推', 'Image to Subject')}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setCreateMode('generate')}
                                        className={px-4 py-2 border-b-2 text-sm font-medium transition-colors }
                                    >
                                        {t('已有实体生成', 'Auto Generate')}
                                    </button>
                                </div>
                            )}
'''

content_wrap_start = '''
                            <div className="p-6 overflow-y-auto custom-scrollbar flex-1 bg-black/10 flex flex-col gap-6">
                                {(!isNew || createMode === 'manual') && (
'''
content_wrap_end = '''
                                )}

                                {isNew && createMode === 'image' && (
                                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                                        {t('待实现：上传图片并自动分析提取角色设定...', 'To be implemented: Upload image and auto-extract subject settings...')}
                                    </div>
                                )}

                                {isNew && createMode === 'generate' && (
                                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                                        {t('待实现：从现有剧本或全局设定中批量构建角色...', 'To be implemented: Auto-build subjects from current script or global settings...')}
                                    </div>
                                )}
'''
# We need to wrap the whole content part.
# Where does it end? Before <!-- Footer --> or <div className="flex justify-between items-center p-6 border-t
# Let's locate it first.

lines = text.splitlines()
out = []
in_modal = False
in_content = False
for i, line in enumerate(lines):
    # we don't want to mess up, let's find the Exact modal
    if '{/* View/Edit Entity Modal */}' in line:
        in_modal = True
        
    out.append(line)

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
