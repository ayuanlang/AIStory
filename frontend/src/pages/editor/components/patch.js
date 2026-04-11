const fs = require('fs');
let code = fs.readFileSync('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'utf8');

code = code.replace(
    '             <AnimatePresence>\n                {editingShot && (\n                    <motion.div',
    '             <AnimatePresence>\n                {editingShot && (() => {\n                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || "16:9";\n                    const aspectParts = parseAspectRatioParts(preferredAspectRatio);\n                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];\n                    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts[0] + "/" + aspectParts[1] } : undefined;\n                    return (\n                    <motion.div'
);

code = code.replace(
    '                    </motion.div>\n                )}\n            </AnimatePresence>',
    '                    </motion.div>\n                    );\n                })()}\n            </AnimatePresence>'
);

code = code.replace(
    '<div className="grid grid-cols-1 lg:grid-cols-3 gap-4">',
    '<div className={isPortrait ? "grid grid-cols-1 gap-6" : "grid grid-cols-1 lg:grid-cols-3 gap-4"}>'
);

// START FRAME
const sOld1 = '                                    {/* Start Frame */}\n                                    <div className="space-y-2">';
const sNew1 = '                                    {/* Start Frame */}\n                                    <div className={isPortrait ? "flex flex-col md:flex-row gap-4" : "space-y-2"}>\n                                        <div className={isPortrait ? "w-full md:w-[40%] space-y-2" : "space-y-2"}>';
code = code.replace(sOld1, sNew1);

const sOld2 = '<div className={spect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors   } onClick={() => openAssetDetailModal(\\'start\\')}>'.replace(/  /g, ''); // exact string might vary
code = code.replace(/<div className=\{\spect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors \$\{currentGeneratingState.start \? 'border-amber-[^]+\} onClick=\{\(\) => openAssetDetailModal\('start'\)\}>/, '<div style={mediaAspectStyle} className={g-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors  } onClick={() => openAssetDetailModal(\\'start\\')}>');


const sOld3 = '<ReferenceManager \n                                            shot={editingShot} \n                                            entities={entities} \n                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} \n                                            title={t(\\'参考图（起始帧）\\', \\'Refs (Start)\\')}';
const sNew3 = '                                      </div>\n                                        <div className={isPortrait ? "w-full md:w-[60%]" : ""}>\n                                        <ReferenceManager \n                                            shot={editingShot} \n                                            entities={entities} \n                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} \n                                            title={t(\\'参考图（起始帧）\\', \\'Refs (Start)\\')}';
code = code.replace(sOld3, sNew3);

const sOld4 = '                                        />\n                                    </div>\n\n\n                                    {/* End Frame */}';
const sNew4 = '                                        />\n                                        </div>\n                                    </div>\n\n\n                                    {/* End Frame */}';
code = code.replace(sOld4, sNew4);


// END FRAME
const eOld1 = '                                    {/* End Frame */}\n                                    <div className="space-y-2">';
const eNew1 = '                                    {/* End Frame */}\n                                    <div className={isPortrait ? "flex flex-col md:flex-row gap-4" : "space-y-2"}>\n                                        <div className={isPortrait ? "w-full md:w-[40%] space-y-2" : "space-y-2"}>';
code = code.replace(eOld1, eNew1);

code = code.replace(/<div className=\{\spect-video bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors \$\{currentGeneratingState.end \? 'border-amber-[^]+\} onClick=\{\(\) => openAssetDetailModal\('end'\)\}>/, '<div style={mediaAspectStyle} className={g-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors  } onClick={() => openAssetDetailModal(\\'end\\')}>');


const eOld3 = '<ReferenceManager \n                                            shot={editingShot} \n                                            entities={entities} \n                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} \n                                            title={t(\\'参考图（结束帧）\\', \\'Refs (End)\\')}';
const eNew3 = '                                      </div>\n                                        <div className={isPortrait ? "w-full md:w-[60%]" : ""}>\n                                        <ReferenceManager \n                                            shot={editingShot} \n                                            entities={entities} \n                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} \n                                            title={t(\\'参考图（结束帧）\\', \\'Refs (End)\\')}';
code = code.replace(eOld3, eNew3);

const eOld4 = '                                        />\n                                    </div>\n\n                                    {/* Final Video Output (Moved Here) */}';
const eNew4 = '                                        />\n                                        </div>\n                                    </div>\n\n                                    {/* Final Video Output (Moved Here) */}';
code = code.replace(eOld4, eNew4);

// VIDEO
const vOld1 = '                                    {/* Final Video Output (Moved Here) */}\n                                    <div className="space-y-2">';
const vNew1 = '                                    {/* Final Video Output (Moved Here) */}\n                                    <div className={isPortrait ? "flex flex-col md:flex-row gap-4" : "space-y-2"}>\n                                        <div className={isPortrait ? "w-full md:w-[40%] space-y-2" : "space-y-2"}>';
code = code.replace(vOld1, vNew1);

const vOld2 = '<div \n                                            className="aspect-video bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center"\n                                            onClick={() => openAssetDetailModal(\\'video\\')}\n                                        >';
const vNew2 = '<div \n                                            style={mediaAspectStyle}\n                                            className={g-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center }\n                                            onClick={() => openAssetDetailModal(\\'video\\')}\n                                        >';
code = code.replace(vOld2, vNew2);

const vOld3 = '<ReferenceManager \n                                            shot={editingShot} \n                                            entities={entities} \n                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} \n                                            title={t(\\'参考图（实体）\\', \\'Refs (Entity)\\')}';
const vNew3 = '                                      </div>\n                                        <div className={isPortrait ? "w-full md:w-[60%]" : ""}>\n                                        <ReferenceManager \n                                            shot={editingShot} \n                                            entities={entities} \n                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} \n                                            title={t(\\'参考图（实体）\\', \\'Refs (Entity)\\')}';
code = code.replace(vOld3, vNew3);

const vOld4 = 'strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || \\'{}\\')) !== \\'entity_refs\\'}\n                                        />\n                                    </div>\n                                </div>\n\n\n                                {/* Keyframes Section (Enhanced) */}';
const vNew4 = 'strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || \\'{}\\')) !== \\'entity_refs\\'}\n                                        />\n                                        </div>\n                                    </div>\n                                </div>\n\n\n                                {/* Keyframes Section (Enhanced) */}';
code = code.replace(vOld4, vNew4);

const kOld = '<div className="aspect-video bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center" onClick={() => openAssetDetailModal(\\'keyframe\\', idx)}>';
const kNew = '<div style={mediaAspectStyle} className={g-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center } onClick={() => openAssetDetailModal(\\'keyframe\\', idx)}>';
code = code.replace(kOld, kNew);

fs.writeFileSync('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', code);
console.log("Patched successfully!");
