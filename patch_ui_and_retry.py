#!/usr/bin/env python3

import re

def patch_script_editor():
    file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern_1 = r'(    const runPostImportSceneSubjectPipeline = useCallback\(.*?\}\);\n    \}\);\n    \}, \[.*?\]\);)'
    
    replacement_1 = r'''\1

    const handleRetryPhase2 = async () => {
        setIsRetryingPhase2(true);
        try {
            await runPostImportSceneSubjectPipeline(analysisUiReport?.importReport || {}, subjectIndexText);
        } catch (error) {
            onLog?.(`Retry Phase 2 failed: ${error.message}`);
        } finally {
            setIsRetryingPhase2(false);
        }
    };'''
    
    # Try a more generic approach if the above fails
    # We can just look for the end of useCallback for runPostImportSceneSubjectPipeline
    idx = content.find('const formatPhaseTime = (ms) =>')
    if idx != -1:
        # insert before formatPhaseTime
        content = content[:idx] + r'''
    const handleRetryPhase2 = async () => {
        setIsRetryingPhase2(true);
        try {
            await runPostImportSceneSubjectPipeline(analysisUiReport?.importReport || {}, subjectIndexText);
        } catch (error) {
            onLog?.(`Retry Phase 2 failed: ${error.message}`);
        } finally {
            setIsRetryingPhase2(false);
        }
    };

''' + content[idx:]

    
    # ===== PATCH 2: Add Phase 2 Subject Index UI section =====
    # Find the logic check line closing and the following divs
    pattern_2 = r'(                                </div>\n                            </div>\n                        </div>)'
    
    replacement_2 = r'''                                </div>
                            </div>
                            
                            {subjectIndexText && (
                                <div className="rounded-lg border border-white/10 bg-black/20 p-4 mt-4">
                                    <div className="font-bold text-white/90 text-sm mb-3 flex items-center gap-2">
                                        📋 {t('Phase 2 Subject Index', 'Phase 2 Subject Index')}
                                    </div>
                                    <div className="space-y-3">
                                        <textarea 
                                            className="w-full h-32 p-3 bg-black/30 border border-white/10 rounded-md text-white/80 font-mono text-xs resize-none focus:outline-none focus:border-white/20"
                                            value={subjectIndexText}
                                            onChange={(e) => {
                                                if (isEditingSubjectIndex) {
                                                    setSubjectIndexText(e.target.value);
                                                }
                                            }}
                                            readOnly={!isEditingSubjectIndex}
                                        />
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setIsEditingSubjectIndex(!isEditingSubjectIndex)}
                                                className="px-3 py-1.5 rounded-md text-xs font-semibold bg-blue-500/20 hover:bg-blue-500/30 border border-blue-400/50 text-blue-300"
                                            >
                                                {isEditingSubjectIndex ? t('完成编辑', 'Done') : t('修改', 'Edit')}
                                            </button>
                                            {isEditingSubjectIndex && (
                                                <button
                                                    onClick={async () => {
                                                        try {
                                                            await updateEpisode(activeEpisode.id, { 
                                                                ai_scene_analysis_subject_index: subjectIndexText 
                                                            });
                                                            onLog?.('Subject Index saved successfully');
                                                            setIsEditingSubjectIndex(false);
                                                        } catch (error) {
                                                            onLog?.(`Failed to save Subject Index: ${error.message}`);
                                                        }
                                                    }}
                                                    className="px-3 py-1.5 rounded-md text-xs font-semibold bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/50 text-emerald-300"
                                                >
                                                    {t('保存', 'Save')}
                                                </button>
                                            )}
                                            <button
                                                onClick={handleRetryPhase2}
                                                disabled={isRetryingPhase2}
                                                className="px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/50 text-amber-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                            >
                                                {isRetryingPhase2 ? (
                                                    <>
                                                        <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
                                                        {t('正在重试...', 'Retrying...')}
                                                    </>
                                                ) : (
                                                    <>
                                                        <RefreshCw className="w-3 h-3 flex-shrink-0" />
                                                        {t('重试第二阶段(资产生成)', 'Retry Phase 2')}
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>'''
    
    content = re.sub(pattern_2, replacement_2, content, count=1)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Patching completed successfully!")

if __name__ == '__main__':
    patch_script_editor()