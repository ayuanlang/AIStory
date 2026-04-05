const fs = require('fs');

const filePath = 'frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf8');
const oldBlock = fs.readFileSync('current_old_version.txt', 'utf8');

const newBlock =                     {analysisUiReport && analysisUiReport.status !== 'running' && (() => {
                        const charCount = Number(analysisUiReport.importReport?.importedSubjectCounts?.character || 0);
                        const envCount = Number(analysisUiReport.importReport?.importedSubjectCounts?.environment || 0);
                        const propCount = Number(analysisUiReport.importReport?.importedSubjectCounts?.prop || 0);
                        const shotCount = Number(analysisUiReport.importReport?.sceneSubjectPostImportReport?.checkedSceneCount || 0);
                        const isZeroResult = charCount === 0 && envCount === 0 && propCount === 0 && shotCount === 0;

                        return (
                            <div className={\ounded-lg border bg-black/20 p-3 text-xs space-y-1.5 mt-2 \\}>
                                <div className={\ont-bold text-base flex items-center gap-2 \\}>
                                    {isZeroResult ? <AlertTriangle className="w-5 h-5 text-red-500" /> : <CheckCircle className="w-5 h-5 text-emerald-400" />}
                                    {isZeroResult ? t('剧本分析结果异常：提取提取失败！', 'Analysis Result Abnormal: Extraction Failed!') : t('剧本分析与导入完成！', 'Analysis & Import Completed!')}
                                </div>
                                
                                {isZeroResult ? (
                                    <div className="text-white/90 bg-red-950/30 p-3 rounded-md border border-red-500/20 space-y-2">
                                        <p>
                                            <span className="font-medium text-red-400">🚨 {t('失败提示', 'Failure Notice')}:</span> {t('检测到大模型返回的内容均为 0（0个角色、0个场景、0个道具、0个镜头）。', 'Detected all 0 results returned by the large model.')}
                                        </p>
                                        <p>
                                            {t('您的剧本似乎未能被大模型正确理解，或返回了不支持的格式内容。', 'Your script might not be understood correctly by the large model or returned an unsupported format.')}
                                        </p>
                                        <p className="text-red-300 font-semibold">
                                            {t('👉 请您重新检查、调整“剧本内容”或“对大模型的补充说明”后，再次点击重试！', '👉 Please check and adjust your script or prompt, then try again!')}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="text-white/80 space-y-2 bg-black/20 p-3 rounded-md border border-white/5">
                                        <div>
                                            <span className="font-medium">✨ {t('新登场资产', 'New Assets')}:</span> {t('为您提炼了', 'Generated')}
                                            <span className="text-purple-300 font-semibold"> {charCount} </span>{t('位角色', 'characters')}、
                                            <span className="text-emerald-300 font-semibold"> {envCount} </span>{t('个场景', 'environments')}、
                                            <span className="text-amber-300 font-semibold"> {propCount} </span>{t('个道具', 'props')}。
                                        </div>
                                        <div>
                                            <span className="font-medium">🔍 {t('镜头画面搭建', 'Scene Construction')}:</span> {t('核对了', 'Checked')}
                                            <span className="text-white font-semibold"> {shotCount} </span>{t('个镜头', 'shots')}。
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
                                )}
                                
                                <div className="text-xs text-white/60 space-y-1 pt-1">
                                    {!isZeroResult && (
                                        <div>
                                            * {t('如果提示有极少数过渡性道具生成失败，您可以直接忽略，不影响视频生成的大局。', 'If a few minor transitional props failed to generate, you can safely ignore them.')}
                                        </div>
                                    )}
                                    <div>
                                        * {t('如果不满意，也可以在刚才的“对大模型优先提示说明”写清要求。', 'Not satisfied? Add notes below.')}
                                    </div>
                                    <div className="text-white/40 pt-2 border-t border-white/5 mt-2">
                                        {t('总生成时间：', 'Total Time: ')} {analysisUiReport.durationMs ? \\ \\ : '--'}
                                    </div>
                                </div>
                            </div>
                        );
                    })()};

if (content.includes(oldBlock)) {
    content = content.replace(oldBlock, newBlock);
    fs.writeFileSync(filePath, content, 'utf8');
    console.log('Success!');
} else {
    console.log('Failed to find oldBlock');
}
