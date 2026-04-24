const fs = require('fs');
const fp = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(fp, 'utf8');

// Target 1: The old analysisUiReport block which was renamed to phase1AnalysisReport
const target1StartStr = "{phase1AnalysisReport && phase1AnalysisReport.status !== 'running' && (";
let target1StartIdx = content.indexOf(target1StartStr);
if (target1StartIdx !== -1) {
    let openCount1 = 0;
    let started1 = false;
    let target1EndIdx = -1;

    for (let i = target1StartIdx; i < content.length; i++) {
        if (content[i] === '{') {
            openCount1++;
            started1 = true;
        } else if (content[i] === '}') {
            openCount1--;
            if (started1 && openCount1 === 0) {
                target1EndIdx = i;
                break;
            }
        }
    }

    if (target1EndIdx !== -1) {
        content = content.slice(0, target1StartIdx) + content.slice(target1EndIdx + 1);
        console.log('Removed Target 1 successfully');
    }
}

// Target 2: The Raw Mode condition
const rawModeStartStr = '{isRawMode ? (';
let startIdx = content.indexOf(rawModeStartStr);

if (startIdx !== -1) {
    let endBraceIdx = -1;
    let openCount = 0;
    let started = false;

    for (let i = startIdx; i < content.length; i++) {
        if (content[i] === '{') {
            openCount++;
            started = true;
        } else if (content[i] === '}') {
            openCount--;
            if (started && openCount === 0) {
                endBraceIdx = i;
                break;
            }
        }
    }

    const tableMatch = content.match(/<table className="w-full text-left border-collapse text-sm">[\s\S]*?<\/table>/);
    if (tableMatch && endBraceIdx !== -1) {
        const tableHTML = tableMatch[0];
        
        const panelJSX = `
        <div className="overflow-auto custom-scrollbar flex-1 w-full">
            ${tableHTML}
        </div>
        <div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 border-t border-white/10 pt-2 overflow-hidden">
            {/* Phase 1 Panel */}
            <div className="flex-1 overflow-hidden">
                <LLMResultPanel
                    title={t('第一阶段解构', 'Phase 1: Analysis')}
                    t={t}
                    report={phase1AnalysisReport}
                    rawText={llmRawResultContent}
                    onRawTextChange={handleLlmRawContentChange}
                    onRawTextBlur={handleSaveLlmRawContent}
                    placeholder={t('第一阶段返回的文本...', 'Phase 1 raw text...')}
                />
            </div>
            {/* Phase 2 Panel */}
            <div className="flex-1 overflow-hidden flex flex-col">
                <LLMResultPanel
                    title={t('第二阶段补充资产', 'Phase 2: Assets')}
                    t={t}
                    report={phase2AnalysisReport}
                    rawText={llmAssetRawResultContent}
                    onRawTextChange={setLlmAssetRawResultContent}
                    placeholder={t('第二阶段返回的实体补充...', 'Phase 2 raw text...')}
                    extraContent={
                        <div className="rounded-lg border border-white/10 bg-black/20 p-2 mt-2 mb-2 w-full shrink-0 flex flex-col min-h-0">
                            <div className="font-bold text-white/90 text-sm mb-1">
                                📋 {t('Subject Index', 'Phase 2 Subject Index')}
                            </div>
                            <div className="flex-1 min-h-0 flex flex-col gap-2">
                                <textarea 
                                    className="w-full flex-1 p-2 bg-black/30 border border-white/10 rounded-md text-white/80 font-mono text-xs resize-none focus:outline-none custom-scrollbar"
                                    value={subjectIndexText}
                                    onChange={(e) => setSubjectIndexText(e.target.value)}
                                    readOnly={!isEditingSubjectIndex}
                                    placeholder={t('粘贴或编辑 Index...', 'Paste Index...')}
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setIsEditingSubjectIndex(!isEditingSubjectIndex)}
                                        className="px-3 py-1 rounded-md text-xs font-semibold bg-blue-500/20 text-blue-300 transition-colors hover:bg-blue-500/30"
                                    >
                                        {isEditingSubjectIndex ? t('完成', 'Done') : t('修改', 'Edit')}
                                    </button>
                                    {isEditingSubjectIndex && (
                                        <button
                                            onClick={async () => {
                                                try {
                                                    await updateEpisode(activeEpisode.id, { ai_scene_analysis_subject_index: subjectIndexText });
                                                    setIsEditingSubjectIndex(false);
                                                } catch (e) {}
                                            }}
                                            className="px-3 py-1 rounded-md text-xs font-semibold bg-emerald-500/20 text-emerald-300 transition-colors hover:bg-emerald-500/30"
                                        >
                                            {t('保存', 'Save')}
                                        </button>
                                    )}
                                    <button
                                        onClick={handleRetryPhase2}
                                        disabled={isPlaying || projectStatus === 'loading' || isAnalyzing}
                                        className="px-3 py-1 font-bold rounded-md text-xs bg-amber-500 hover:bg-amber-400 text-black ml-auto disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {t('基于已有的 Index 重跑实体生成', 'Run Phase 2 on Index')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    }
                />
            </div>
        </div>
`.trim();

        content = content.slice(0, startIdx) + panelJSX + content.slice(endBraceIdx + 1);
        console.log('Removed Target 2 (ternary) and injected Table + Panels successfully');
    } else {
        console.log('Failed to match table!');
    }
}

fs.writeFileSync(fp, content);
console.log('File patched!');

