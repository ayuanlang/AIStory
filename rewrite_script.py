import os
import re

file_path = r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. AnimatePresence wrapper and isPortrait calculation
p1_old = '''             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (
                    <motion.div'''
p1_new = '''             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio);
                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];
                    const mediaAspectStyle = isPortrait ? { aspectRatio: f"{aspectParts[0]}/{aspectParts[1]}" } : undefined;
                    return (
                    <motion.div'''

p2_old = '''                    </motion.div>
                )}
            </AnimatePresence>'''
p2_new = '''                    </motion.div>
                    );
                })()}
            </AnimatePresence>'''

text = text.replace(p1_old, p1_new)
text = text.replace(p2_old, p2_new)


# 2. Main grid layout
p3_old = '''                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">'''
p3_new = '''                                {/* 3 Column Layout: Start | End | Video */}
                                <div className={isPortrait ? "grid grid-cols-1 gap-6" : "grid grid-cols-1 lg:grid-cols-3 gap-4"}>'''
text = text.replace(p3_old, p3_new)

# 3. Start Frame Layout
p4_old = '''                                    {/* Start Frame */}
                                    <div className="space-y-2">'''
p4_new = '''                                    {/* Start Frame */}
                                    <div className={isPortrait ? "flex flex-col xl:flex-row gap-4" : "space-y-2"}>
                                        <div className={isPortrait ? "w-full xl:w-[45%] space-y-2" : "space-y-2"}>'''
text = text.replace(p4_old, p4_new)

# Start Image aspect-video check
text = text.replace(
    '''<div className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('start')}>''',
    '''<div style={mediaAspectStyle} className={`bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${!isPortrait ? 'aspect-video' : ''} ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('start')}>'''
)

# Start ReferenceManager wrap
text = re.sub(
    r'(\s*)(<ReferenceManager \s*shot=\{editingShot\} \s*entities=\{entities\} \s*onUpdate=\{\(updates\) => \{ persistEditingShotUpdates\(updates\); \}\} \s*title=\{t\(\'参考图（起始帧）\', \'Refs \(Start\)\'\)\})',
    r'\1</div>\1<div className={isPortrait ? "w-full xl:w-[55%]" : ""}>\1\2',
    text
)

p6_old = '''                                        />
                                    </div>


                                    {/* End Frame */}'''
p6_new = '''                                        />
                                        </div>
                                    </div>


                                    {/* End Frame */}'''
text = text.replace(p6_old, p6_new)

# 4. End Frame Layout
p7_old = '''                                    {/* End Frame */}
                                    <div className="space-y-2">'''
p7_new = '''                                    {/* End Frame */}
                                    <div className={isPortrait ? "flex flex-col xl:flex-row gap-4" : "space-y-2"}>
                                        <div className={isPortrait ? "w-full xl:w-[45%] space-y-2" : "space-y-2"}>'''
text = text.replace(p7_old, p7_new)

text = text.replace(
    '''<div className={`aspect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('end')}>''',
    '''<div style={mediaAspectStyle} className={`bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${!isPortrait ? 'aspect-video' : ''} ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('end')}>'''
)

text = re.sub(
    r'(\s*)(<ReferenceManager \s*shot=\{editingShot\} \s*entities=\{entities\} \s*onUpdate=\{\(updates\) => \{ persistEditingShotUpdates\(updates\); \}\} \s*title=\{t\(\'参考图（结束帧）\', \'Refs \(End\)\'\)\})',
    r'\1</div>\1<div className={isPortrait ? "w-full xl:w-[55%]" : ""}>\1\2',
    text
)

p8_old = '''                                        />
                                    </div>

                                    {/* Final Video Output (Moved Here) */}'''
p8_new = '''                                        />
                                        </div>
                                    </div>

                                    {/* Final Video Output (Moved Here) */}'''
text = text.replace(p8_old, p8_new)


# 5. Video Layout
p9_old = '''                                    {/* Final Video Output (Moved Here) */}
                                    <div className="space-y-2">'''
p9_new = '''                                    {/* Final Video Output (Moved Here) */}
                                    <div className={isPortrait ? "flex flex-col xl:flex-row gap-4" : "space-y-2"}>
                                        <div className={isPortrait ? "w-full xl:w-[45%] space-y-2" : "space-y-2"}>'''
text = text.replace(p9_old, p9_new)

p10_old = '''<div 
                                            className="aspect-video bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center"
                                            onClick={() => openAssetDetailModal('video')}
                                        >'''
p10_new = '''<div 
                                            style={mediaAspectStyle}
                                            className={`bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center ${!isPortrait ? 'aspect-video' : ''}`}
                                            onClick={() => openAssetDetailModal('video')}
                                        >'''
text = text.replace(p10_old, p10_new)

text = re.sub(
    r'(\s*)(<ReferenceManager \s*shot=\{editingShot\} \s*entities=\{entities\} \s*onUpdate=\{\(updates\) => \{ persistEditingShotUpdates\(updates\); \}\} \s*title=\{t\(\'参考图（实体）\', \'Refs \(Entity\)\'\)\})',
    r'\1</div>\1<div className={isPortrait ? "w-full xl:w-[55%]" : ""}>\1\2',
    text
)

p11_old = '''                                            strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || '{}')) !== 'entity_refs'}
                                        />
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}'''
p11_new = '''                                            strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || '{}')) !== 'entity_refs'}
                                        />
                                        </div>
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}'''
text = text.replace(p11_old, p11_new)

# 6. Keyframes Layout
p12_old = '''<div className="aspect-video bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center" onClick={() => openAssetDetailModal('keyframe', idx)}>'''
p12_new = '''<div style={mediaAspectStyle} className={`bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center ${!isPortrait ? 'aspect-video' : ''}`} onClick={() => openAssetDetailModal('keyframe', idx)}>'''
text = text.replace(p12_old, p12_new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Rewrite Script Completed!")
