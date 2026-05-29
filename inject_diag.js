const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
const lines = fs.readFileSync(filePath, 'utf-8').split('\n');

const block = `            <div className="mb-4 rounded-xl border border-white/10 bg-black/20 p-4">
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
                                        <button onClick={() => handleRetryPhase2({})} disabled={isAnalyzing || isRetryingPhase2} className="text-[10px] px-1 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 disabled:opacity-50">
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
            </div>`;

for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('analysisFlowStatus.phase !== \'idle\'') && lines[i].includes('analysisFlowStatusHistory.length > 0')) {
        lines.splice(i, 0, block);
        break;
    }
}
fs.writeFileSync(filePath, lines.join('\n'), 'utf-8');
console.log('injected');