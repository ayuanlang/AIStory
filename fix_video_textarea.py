import sys

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_video_textareas = '''                                                                </div>
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold">
                                                                    {showCnPrompt ? t('中文提示词', 'Prompt (CN)') : t('英文提示词', 'Prompt (EN)')}
                                                                </div>
                                                                <textarea       
                                                                    className="w-full h-56 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                    value={videoPromptText}
                                                                    onChange={(e) => {
                                                                        if (showCnPrompt) {
                                                                            updateTechField('video_prompt_cn', e.target.value);
                                                                            return;
                                                                        }       
                                                                        setEditingShot({ ...editingShot, ...buildVideoPromptEnUpdates(e.target.value) });       
                                                                    }}
                                                                />
                                                                <RefineControl originalText={videoPromptText} onUpdate={(v) => {
                                                                    if (showCnPrompt) {
                                                                        updateTechField('video_prompt_cn', v);
                                                                        return; 
                                                                    }
                                                                    setEditingShot({ ...editingShot, ...buildVideoPromptEnUpdates(v) });
                                                                }} type="video" />'''

new_video_textareas = '''                                                                </div>
                                                                <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-4">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">
                                                                        {t('英文提示词', 'Prompt (EN)')}
                                                                    </div>
                                                                    <textarea       
                                                                        className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={getShotVideoPromptEn(editingShot)}
                                                                        onChange={(e) => {
                                                                            setEditingShot({ ...editingShot, ...buildVideoPromptEnUpdates(e.target.value) });       
                                                                        }}
                                                                    />
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                        {t('中文提示词', 'Prompt (CN)')}
                                                                    </div>
                                                                    <textarea       
                                                                        className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={tech.video_prompt_cn || ''}
                                                                        onChange={(e) => {
                                                                            updateTechField('video_prompt_cn', e.target.value);
                                                                        }}
                                                                    />
                                                                    <RefineControl originalText={showCnPrompt ? (tech.video_prompt_cn || '') : getShotVideoPromptEn(editingShot)} onUpdate={(v) => {
                                                                        if (showCnPrompt) {
                                                                            updateTechField('video_prompt_cn', v);
                                                                            return; 
                                                                        }
                                                                        setEditingShot({ ...editingShot, ...buildVideoPromptEnUpdates(v) });
                                                                    }} type="video" />
                                                                </div>'''

text = text.replace(old_video_textareas, new_video_textareas)

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
