import re

file_path = r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Variables Injection
content = content.replace(
'''             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (
                    <motion.div''',
'''             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio);
                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];
                    const mediaAspectStyle = isPortrait ? { aspectRatio: f"{aspectParts[0]}/{aspectParts[1]}" } : undefined;
                    
                    return (
                    <motion.div'''
)

content = content.replace(
'''                            </motion.div>
                )}
            </AnimatePresence>''',
'''                            </motion.div>
                    );
                })()}
            </AnimatePresence>'''
)

# 2. Layout
content = content.replace(
'''                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">''',
'''                                {/* 3 Column Layout: Start | End | Video */}
                                <div className={isPortrait ? "grid grid-cols-1 gap-6" : "grid grid-cols-1 lg:grid-cols-3 gap-4"}>'''
)

# Replace the layout logic for each column.

# START FRAME
start_frame_old = '''                                        </div>
                                        {currentGeneratingState.start && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">'''
start_frame_new = '''                                        </div>
                                        <div className={isPortrait ? "flex flex-col md:flex-row gap-4" : "space-y-2"}>
                                            <div className={isPortrait ? "w-full md:w-[40%] space-y-2" : "space-y-2"}>
                                        {currentGeneratingState.start && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">'''

content = content.replace(start_frame_old, start_frame_new)
start_img_old = '''                                        <div className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('start')}>'''
start_img_new = '''                                        <div style={mediaAspectStyle} className={`bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${!isPortrait ? 'aspect-video' : ''} ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('start')}>'''
content = content.replace(start_img_old, start_img_new)

start_close_old = '''                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities}'''
start_close_new = '''                                            </div>
                                            <div className={isPortrait ? "w-full md:w-[60%]" : ""}>
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities}'''
content = content.replace(start_close_old, start_close_new)

start_mgr_old = '''                                                }
                                            }}
                                        />
                                    </div>


                                    {/* End Frame */}'''
start_mgr_new = '''                                                }
                                            }}
                                        />
                                            </div>
                                        </div>
                                    </div>


                                    {/* End Frame */}'''
content = content.replace(start_mgr_old, start_mgr_new)


# END FRAME
end_frame_old = '''                                        </div>
                                        {currentGeneratingState.end && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">'''
end_frame_new = '''                                        </div>
                                        <div className={isPortrait ? "flex flex-col md:flex-row gap-4" : "space-y-2"}>
                                            <div className={isPortrait ? "w-full md:w-[40%] space-y-2" : "space-y-2"}>
                                        {currentGeneratingState.end && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">'''
content = content.replace(end_frame_old, end_frame_new)
end_img_old = '''                                        <div className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('end')}>'''
end_img_new = '''                                        <div style={mediaAspectStyle} className={`bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${!isPortrait ? 'aspect-video' : ''} ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('end')}>'''
content = content.replace(end_img_old, end_img_new)

# end mgr is same signature
end_mgr_old = '''                                                }
                                            }}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图（结束帧）', 'Refs (End)')}
                                            promptText={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.end_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.end_frame || '')}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="end_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                    </div>

                                    {/* Final Video Output (Moved Here) */}'''
end_mgr_new = '''                                                }
                                            }}
                                        />
                                            </div>
                                            <div className={isPortrait ? "w-full md:w-[60%]" : ""}>
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图（结束帧）', 'Refs (End)')}
                                            promptText={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.end_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.end_frame || '')}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="end_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                            </div>
                                        </div>
                                    </div>

                                    {/* Final Video Output (Moved Here) */}'''
content = content.replace(end_mgr_old, end_mgr_new)


# VIDEO
video_frame_old = '''                                            </div>
                                        </div>

                                        <div 
                                            className="aspect-video bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center"
                                            onClick={() => openAssetDetailModal('video')}
                                        >'''
video_frame_new = '''                                            </div>
                                        </div>
                                        <div className={isPortrait ? "flex flex-col md:flex-row gap-4" : "space-y-2"}>
                                            <div className={isPortrait ? "w-full md:w-[40%] space-y-2" : "space-y-2"}>
                                        <div 
                                            style={mediaAspectStyle}
                                            className={`bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center ${!isPortrait ? 'aspect-video' : ''}`}
                                            onClick={() => openAssetDetailModal('video')}
                                        >'''
content = content.replace(video_frame_old, video_frame_new)

video_mgr_old = '''                                                }
                                            }}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图（实体）', 'Refs (Entity)')}
                                            promptText={`${getShotVideoPromptEn(editingShot) || ''}\\n${(() => { try { return String(JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''); } catch (e) { return ''; } })()}`}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="video_ref_image_urls"
                                            strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || '{}')) !== 'entity_refs'}
                                        />
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}'''
video_mgr_new = '''                                                }
                                            }}
                                        />
                                            </div>
                                            <div className={isPortrait ? "w-full md:w-[60%]" : ""}>
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图（实体）', 'Refs (Entity)')}
                                            promptText={`${getShotVideoPromptEn(editingShot) || ''}\\n${(() => { try { return String(JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''); } catch (e) { return ''; } })()}`}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="video_ref_image_urls"
                                            strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || '{}')) !== 'entity_refs'}
                                        />
                                            </div>
                                        </div>
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}'''
content = content.replace(video_mgr_old, video_mgr_new)

# KEYFRAMES - "以能让图片与视频的显示框也能按竖版的方式显示"
kf_img_old = '''                                                {/* Image Area */}
                                                <div className="aspect-video bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center" onClick={() => openAssetDetailModal('keyframe', idx)}>'''
kf_img_new = '''                                                {/* Image Area */}
                                                <div style={mediaAspectStyle} className={`bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center ${!isPortrait ? 'aspect-video' : ''}`} onClick={() => openAssetDetailModal('keyframe', idx)}>'''
content = content.replace(kf_img_old, kf_img_new)


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced content successfully.")
