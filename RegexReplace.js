const fs = require("fs");
const file = "c:\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx";
let content = fs.readFileSync(file, 'utf8');

const regex = /{analysisUiReport && analysisUiReport.status !== 'running' && \([\s\S]*?(?=<div className="p-4 border-t border-white\/10)/;

const match = content.match(regex);
if (match) {
    const replacement = `{analysisUiReport && analysisUiReport.status !== 'running' && (
                        <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm space-y-3 mb-2">
                            <div className="font-bold text-white/90 text-base flex items-center gap-2">
                                <CheckCircle className="w-5 h-5 text-emerald-400" /> {t('剧本分析与导入完成！', 'Analysis & Import Completed!')}
                            </div>
                            <div className="text-white/80 space-y-2 bg-black/20 p-3 rounded-md border border-white/5">
                                <div>
                                    <span className="font-medium">✨ {t('新登场资产', 'New Assets')}:</span> {t('为您提炼了', 'Generated')}
                                    <span className="text-purple-300 font-semibold"> {analysisUiReport.importReport?.importedSubjectCounts?.character || 0} </span>{t('位角色', 'characters')}、
                                    <span className="text-emerald-300 font-semibold"> {analysisUiReport.importReport?.importedSubjectCounts?.environment || 0} </span>{t('个场景', 'environments')}、
                                    <span className="text-amber-300 font-semibold"> {analysisUiReport.importReport?.importedSubjectCounts?.prop || 0} </span>{t('个道具', 'props')}。
                                </div>
                                <div>
                                    <span className="font-medium">🔍 {t('镜头画面搭建', 'Scene Construction')}:</span> {t('核对了', 'Checked')}
                                    <span className="text-white font-semibold"> {analysisUiReport.importReport?.sceneSubjectPostImportReport?.checkedSceneCount || 0} </span>{t('个镜头', 'shots')}。
                                    {analysisUiReport.importReport?.sceneSubjectPostImportReport?.missingItemCount > 0 ? (
                                        <span className="ml-1 break-all">
                                            {t('其中', 'Among them,')} <span className="text-red-300">{analysisUiReport.importReport?.sceneSubjectPostImportReport?.missingItemCount}</span> {t('个画面细节原本是缺失的，系统已自动帮您生成填补了', 'missing visual details were automatically generated and filled:')} <span className="text-emerald-300">{analysisUiReport.importReport?.sceneSubjectPostImportReport?.supplementReport?.createdItems?.length || 0}</span> {t('个实体', 'entities')}。
                                        </span>
                                    ) : (
                                        <span className="ml-1 text-emerald-300/90">{t('所有画面元素完整，随时可以直接生成画面。', 'All visual elements are complete and ready for generation.')}</span>
                                    )}
                                </div>
                                <div>
                                    <span className="font-medium">💡 {t('逻辑连贯性', 'Logic Check')}:</span> {  
                                        subjectConsistencyReport
                                            ? (subjectConsistencyReport.ok ? <span className="text-emerald-400">{t('逻辑清晰，可以直接推进到下一环节（分镜生成）。', 'Logic is clear, ready to proceed to shot generation.')}</span> : <span className="text-amber-400">{t('发现部分实体可能存在指代不清，建议稍作人工核对。', 'Found some ambiguous entities, quick manual review recommended.')}</span>)
                                            : <span className="text-emerald-400">{t('基础逻辑检查通过。', 'Basic logic check passed.')}</span>
                                    }
                                </div>
                            </div>
                            <div className="text-xs text-white/60 space-y-1 pt-1">
                                <div>
                                    * {t('如果提示有极少数过渡性道具生成失败，您可以直接忽略，不影响视频生成的大局。', 'If a few minor transitional props failed to generate, you can safely ignore them.')}
                                </div>
                                <div>
                                    * {t('如果不满意，也可以在刚才的“补充说明”写清要求，点击下方的“修改并重跑分析”。', 'Not satisfied? Add notes below and click "Refine" to try again.')}
                                </div>
                            </div>
                        </div>
                    )}\n                    `;

    content = content.replace(regex, replacement);
    fs.writeFileSync(file, content);
    console.log("Replaced with regex successfully!");
} else {
    console.log("Could not find the target block using regex.");
}
