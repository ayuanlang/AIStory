const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

// 1. Inject Workflow Diagnostics
const diagBlock = `            <div className="mb-4 rounded-xl border border-white/10 bg-black/20 p-4">
                <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-sm shrink-0">
                        <div className="w-1 h-5 bg-purple-500 rounded-full"></div>
                        {t('进度诊断面板', 'Workflow Diagnostics')}
                    </div>
                    <div className="flex-1 w-full flex items-center justify-between relative max-w-2xl px-4 mt-2 md:mt-0">
                        <div className="absolute top-4 left-8 right-8 h-0.5 bg-white/10 -z-10"></div>
                        
                        <div className="flex flex-col items-center gap-2">
                            <div className={\`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border \${!!getStageOutputContent('stage1', 'optimized_script') ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-white/5 border-white/20 text-white/50'}\`}>
                                {!!getStageOutputContent('stage1', 'optimized_script') ? <Check className="w-4 h-4" /> : 1}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('阶段1: 剧本结构', 'Stage 1: Script')}</span>
                                {!!getStageOutputContent('stage1', 'optimized_script') ? (
                                    <span className="text-[10px] text-emerald-400/80">{t('已具备', 'Ready')}</span>
                                ) : (
                                    <span className="text-[10px] text-white/30">{t('等待中', 'Pending')}</span>
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col items-center gap-2">
                            <div className={\`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border \${!!getStageOutputContent('stage2', 'subject_index') ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : (!!getStageOutputContent('stage1', 'optimized_script') ? 'bg-purple-500/20 border-purple-500/50 text-purple-300' : 'bg-white/5 border-white/20 text-white/50')}\`}>
                                {!!getStageOutputContent('stage2', 'subject_index') ? <Check className="w-4 h-4" /> : 2}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('阶段2: 场景提取', 'Stage 2: Scenes')}</span>
                                {!!getStageOutputContent('stage2', 'subject_index') ? (
                                     <div className="flex items-center gap-1">
                                         <span className="text-[10px] text-emerald-400/80">{t('已具备', 'Ready')}</span>
                                         <button onClick={handleRestartStage2} disabled={isAnalyzing} className="text-[10px] px-1 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 disabled:opacity-50">
                                            {t('重跑', 'Rerun')}
                                         </button>
                                     </div>
                                ) : (
                                    !!getStageOutputContent('stage1', 'optimized_script') ? (
                                        <button onClick={handleRestartStage2} disabled={isAnalyzing} className="text-[10px] px-2 py-0.5 rounded border border-purple-500/50 text-purple-200 bg-purple-500/20 hover:bg-purple-500/30 transition-colors shadow-sm disabled:opacity-50">
                                            {t('前置具备, 点此重跑', 'Ready (Click to Rerun)')}
                                        </button>
                                    ) : (
                                        <span className="text-[10px] text-white/30">{t('缺乏前置', 'Needs Stage 1')}</span>
                                    )
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col items-center gap-2">
                             <div className={\`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border \${!!getStageOutputContent('stage3', 'asset_design_json') ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : (!!getStageOutputContent('stage2', 'subject_index') ? 'bg-purple-500/20 border-purple-500/50 text-purple-300' : 'bg-white/5 border-white/20 text-white/50')}\`}>
                                {!!getStageOutputContent('stage3', 'asset_design_json') ? <Check className="w-4 h-4" /> : 3}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('阶段3: 资产设计', 'Stage 3: Assets')}</span>
                                {!!getStageOutputContent('stage3', 'asset_design_json') ? (
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] text-emerald-400/80">{t('已具备', 'Ready')}</span>
                                        <button onClick={() => handleRetryPhase2({})} disabled={isAnalyzing || isRetryingPhase2} className="text-[10px] px-1 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 disabled:opacity-50 flex items-center gap-1">
                                            {isRetryingPhase2 ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                            {t('重跑', 'Rerun')}
                                        </button>
                                    </div>
                                ) : (
                                    !!getStageOutputContent('stage2', 'subject_index') ? (
                                        <button onClick={() => handleRetryPhase2({})} disabled={isAnalyzing || isRetryingPhase2} className="text-[10px] px-2 py-0.5 rounded border border-purple-500/50 text-purple-200 bg-purple-500/20 hover:bg-purple-500/30 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1">
                                            {isRetryingPhase2 ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                            {t('前置具备, 点此重跑', 'Ready (Click to Rerun)')}
                                        </button>
                                    ) : (
                                        <span className="text-[10px] text-white/30">{t('缺乏前置', 'Needs Stage 2')}</span>
                                    )
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>\n`;

const injectPoint = /\{\(analysisFlowStatus\.phase !== 'idle' \|\| analysisUiReport \|\| analysisFlowStatusHistory\.length > 0\) && \(/;
content = content.replace(injectPoint, diagBlock + "            {(analysisFlowStatus.phase !== 'idle' || analysisUiReport || analysisFlowStatusHistory.length > 0) && (");

// 2. Merge LLM Result Panels
const oldPanelsBlock = /<div className="flex gap-4 h-1\/3 min-h-\[250px\] shrink-0 mt-4 border-t border-white\/10 pt-4 px-6 pb-6">[\s\S]*?{x\/\* Stage 1 Panel \*\/[\s\S]*?<\/div>\s*<\/div>/;
const oldPanelsBlockStr = content.substring(content.indexOf('<div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 mt-4 border-t border-white/10 pt-4 px-6 pb-6">'), content.indexOf('</div>\n            </div>\n\n            {jsonEntityDetailModal.open && (') - 21); // Find the exact end

const mergedPanelBlock = `<div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 mt-4 border-t border-white/10 pt-4 px-6 pb-6">
        <div className="flex-1 overflow-hidden" style={{ minWidth: 0 }}>
            <LLMResultPanel
                title={t('AI 拆解产物', 'AI Analysis Artifacts')}
                t={t}
                stageCards={[...stage1StageCards, ...stage2StageCards, ...stage3StageCards]}
                placeholder={t('分析产物将在此展示...', 'Pipeline outputs...')}
            />
        </div>
    </div>`;

// Safely manually replace it
let startIdx = content.indexOf('<div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 mt-4 border-t border-white/10 pt-4 px-6 pb-6">');
let endStr = '</div>\n        {/* Stage 3 Panel */}';
let endIdx = content.indexOf(endStr);
if (startIdx > -1 && endIdx > -1) {
    let finalEndIdx = content.indexOf('</div>\n    </div>', endIdx);
    if (finalEndIdx > -1) {
        content = content.substring(0, startIdx) + mergedPanelBlock + content.substring(finalEndIdx + 16);
    }
}

// 3. String Fixes
content = content.replace(/badge: adaptedScript \? t\('可回填', 'Re-importable'\) : t\('待输出', 'Pending'\)/g, "badge: adaptedScript ? t('展开可回填', 'Re-importable') : t('展开待输出', 'Pending')");
content = content.replace(/label: t\('回填剧本', 'Restore Script'\)/g, "label: t('回填剧本重跑覆盖', 'Restore & Rerun')");

content = content.replace(/badge: visualBackfillJson \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/g, "badge: visualBackfillJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");

content = content.replace(/badge: sceneMarkdown \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/g, "badge: sceneMarkdown ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");
content = content.replace(/label: t\('重新导入', 'Re-import'\)/g, "label: t('重新导入重跑覆盖', 'Re-import & Rerun')");

content = content.replace(/badge: subjectIndex \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/g, "badge: subjectIndex ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");

content = content.replace(/badge: assetDesignJson \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/g, "badge: assetDesignJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");
content = content.replace(/label: t\('全部导入', 'Import All'\)/g, "label: t('全部导入重跑全部', 'Import All & Rerun')");

content = content.replace(/btnZh: '重跑 道具'/g, "btnZh: '局部导入重跑道具'");
content = content.replace(/btnZh: ' 重跑封面'/g, "btnZh: '局部导入重跑封面'");

// 4. Fix Stage 3 Partials buttons inside loop
const partsStrToReplace = `actions: [
                    {
                        key: \`reimport-stage3-\${cat.key}\`,
                        label: t('局部导入', 'Import Partial'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: catJson,
                            importType: 'json',
                            label: \`stage3 \${cat.key} json\`,
                            importOptions: {
                                subjectsJson: catObj || null,
                                suppressAlerts: false,
                            },
                        }),
                        disabled: isAnalyzing || !catJson,
                        loading: false,
                    },
                    {
                        key: \`restart-stage3-\${cat.key}\`,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'repeat',
                        onClick: () => handleRetryPhase2({ targetEntityTypes: [cat.key] }),
                        disabled: isAnalyzing || isRetryingPhase2 || !getStageOutputContent('stage2', 'subject_index'),
                        loading: isRetryingPhase2 && phase2RetryOptionsRef.current?.targetEntityTypes?.includes(cat.key),
                    }
                ],`;

const newActionsPart = `actions: [
                    {
                        key: \`reimport-stage3-\${cat.key}-and-rerun\`,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'refresh',
                        onClick: async () => {
                            await handleImportStageArtifact({
                                content: catJson,
                                importType: 'json',
                                label: \`stage3 \${cat.key} json\`,
                                importOptions: {
                                    subjectsJson: catObj || null,
                                    suppressAlerts: false,
                                },
                            });
                            handleRetryPhase2({ targetEntityTypes: [cat.key] });
                        },
                        disabled: isAnalyzing || isRetryingPhase2 || !catJson || !getStageOutputContent('stage2', 'subject_index'),
                        loading: isRetryingPhase2 && (phase2RetryOptionsRef.current?.targetEntityTypes?.includes(cat.key)),
                    }
                ],`;

content = content.replace(partsStrToReplace, newActionsPart);
content = content.replace(/badge: catJson \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/g, "badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");

fs.writeFileSync(filePath, content, 'utf-8');
console.log('Final complete fix done.');
