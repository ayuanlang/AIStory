const fs = require('fs');
const fp = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(fp, 'utf8');

// Target 1: The old analysisUiReport block which was renamed to phase1AnalysisReport
// Let's remove the block displaying phase1AnalysisReport at the top
const regexOldReport = /\{phase1AnalysisReport && phase1AnalysisReport\.status !== 'running' && \([\s\S]*?\)\}/s;
content = content.replace(regexOldReport, '');

// Target 2: The Raw Mode condition
// Find {isRawMode ? ( ... ) : ( ... )} and transform it
// The structure is roughly:
// {isRawMode ? (
//     <div className="h-full w-full flex flex-col overflow-hidden">
//     ...
//     </div>
// ) : (
//     <div className="overflow-auto custom-scrollbar h-full w-full">
//        <table className="w-full text-left border-collapse text-sm">
//        ...
//     </div>
// )}

const rawModeStartStr = '{isRawMode ? (';
let startIdx = content.indexOf(rawModeStartStr);

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

const tableStart = content.indexOf('<table className="w-full text-left border-collapse text-sm">');
const tableDivStr = '<div className="overflow-auto custom-scrollbar h-full w-full">';
const tableDivStart = content.lastIndexOf(tableDivStr, tableStart);

let endTableBraceIdx = -1;
let openT = 0;
let startT = false;

for (let i = tableDivStart; i < content.length; i++) {
    if (content.slice(i, i+4) === '<div') {
        openT++;
        startT = true;
    } else if (content.slice(i, i+5) === '</div') {
        openT--;
        if (startT && openT === 0) {
            // Find the closing bracket for the ternary operator `)` followed by `}`
            const rest = content.slice(i);
            const closeBracket = rest.indexOf(')');
            const closeBrace = rest.indexOf('}', closeBracket);
            endTableBraceIdx = i + closeBrace;
            break;
        }
    }
}

// We want to extract JUST the table part entirely and drop the {isRawMode ? ... : ...} shell.
// The table block is the second part of the ternary operator. Let's just find the table div block,
// and extract it. 
// Wait, the table block itself is `<div className="overflow-auto ..."> ... </div>`.

// Just keep the table block and put the panels below it.
// The parent is:
// <div className="flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col">
//     <div className="flex-1 overflow-hidden">
//        ... ternary goes here ...
//     </div>
// </div>

const parentStart = '<div className="flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col">';
const rawContainerEnd = content.indexOf('</div>', endTableBraceIdx);

const panelJSX = `
    <div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 mt-4 border-t border-white/10 pt-4">
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
        <div className="flex-1 overflow-hidden">
            <LLMResultPanel
                title={t('第二阶段补充资产', 'Phase 2: Assets')}
                t={t}
                report={phase2AnalysisReport}
                rawText={llmAssetRawResultContent}
                onRawTextChange={setLlmAssetRawResultContent}
                placeholder={t('第二阶段返回的实体补充...', 'Phase 2 raw text...')}
                extraContent={
                    <div className="rounded-lg border border-white/10 bg-black/20 p-4 mt-2">
                        <div className="font-bold text-white/90 text-sm mb-3">
                            📋 {t('Subject Index', 'Phase 2 Subject Index')}
                        </div>
                        <div className="space-y-3">
                            <textarea 
                                className="w-full h-32 p-3 bg-black/30 border border-white/10 rounded-md text-white/80 font-mono text-xs resize-none focus:outline-none"
                                value={subjectIndexText}
                                onChange={(e) => setSubjectIndexText(e.target.value)}
                                readOnly={!isEditingSubjectIndex}
                                placeholder={t('粘贴或编辑 Index...', 'Paste Index...')}
                            />
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setIsEditingSubjectIndex(!isEditingSubjectIndex)}
                                    className="px-3 py-1.5 rounded-md text-xs font-semibold bg-blue-500/20 text-blue-300"
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
                                        className="px-3 py-1.5 rounded-md text-xs font-semibold bg-emerald-500/20 text-emerald-300"
                                    >
                                        {t('保存', 'Save')}
                                    </button>
                                )}
                                <button
                                    onClick={handleRetryPhase2}
                                    disabled={isPlaying || projectStatus === 'loading' || isAnalyzing}
                                    className="px-3 py-1.5 font-bold rounded-lg text-[11px] bg-amber-500 text-black ml-auto"
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

// Actually replacing the ternary safely is hard. Let's find exactly what to slice.
// We can find the <table> block
const tableMatch = content.match(/<table className="w-full text-left border-collapse text-sm">[\s\S]*?<\/table>/);
if (tableMatch) {
    const tableHTML = tableMatch[0];
    
    // We also need the isRawMode block replaced completely
    const rawModeBlockRegex = /\{isRawMode \? \([\s\S]*?\) : \([\s\S]*?<\/table>\s*<\/div>\s*\)\}/s;
    content = content.replace(rawModeBlockRegex, 
        `
        <div className="overflow-auto custom-scrollbar flex-1 w-full">
            ${tableHTML}
        </div>
        ${panelJSX}
        `
    );
}

fs.writeFileSync(fp, content);
console.log('patched ternary done');
