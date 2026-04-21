const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'frontend/src/pages/editor/components/ScriptEditor.jsx');
let content = fs.readFileSync(filePath, 'utf8');

const hookStartRegex = /const resumeAnalysisFromTaskMarker = useCallback\(async \(marker\) => \{\s*if \(\!activeEpisode\?\.id \|\| \!marker\?\.taskId\) return;\s*if \(analysisResumeInFlightRef\.current \|\| analysisRunInFlightRef\.current\) return;\s*analysisResumeInFlightRef\.current = true;\s*const startedAt = Number\(marker\?\.startedAt \|\| Date\.now\(\)\);/s;

let match = content.match(hookStartRegex);
if (!match) {
    console.error("Hook start regex not matched!");
    process.exit(1);
}

let hookStart = match[0];

const phase2Injection = `        if (marker?.phase === 2) {
            setIsAnalyzing(false);
            setIsRetryingPhase2(true);
            setActiveAnalysisTaskId(String(marker?.taskId || '').trim());
            setAnalysisFlowStatus({
                phase: 'generating_assets',
                message: t("✨ 发现有个没完成的第二阶段任务，正在为您继续生成对应的人物和场景资产...", "Resuming Phase 2 asset generation..."),
            });
            try {
                const result = await awaitAnalyzeSceneWithRecovery(
                    () => waitForAsyncTask(marker.taskId, { interval: 2500, timeout: remainingTimeoutMs }),
                    { startedAt, baselineText: '' }
                );
                const analyzedText = extractAnalysisTextFromResult(result);
                setLlmAssetRawResultContent(analyzedText);

                if (analyzedText) {
                    const hasValidSubjectJsonBlock = /"characters"\s*:\s*\\[|"props"\s*:\s*\\[|"environments"\s*:\s*\\[|"posters"\s*:\s*\\[/i.test(analyzedText);
                    const backendSubjectsJson = result?.subjects_json;
                    if (!hasValidSubjectJsonBlock && !backendSubjectsJson) {
                        onLog?.(\`[Asset Gen Tracking] Warning: AI did not return a valid Entities JSON block during Phase 2 recovery.\`);
                    } else {
                        const sceneImportReport = await doImportText(analyzedText, 'json', {
                            onLog,
                            projectId,
                            episodeId: activeEpisode?.id,
                            subjectsJson: backendSubjectsJson || null,
                            suppressAlerts: true,
                        });
                        
                        setAnalysisUiReport(prev => {
                            const prevImport = prev?.importReport || { importedSceneRows: [] };
                            return {
                                status: 'completed',
                                startedAt,
                                durationMs: Date.now() - startedAt,
                                phaseTimings: null,
                                warning: '',
                                error: '',
                                runtimeMeta: null,
                                importReport: {
                                    ...prevImport,
                                    sceneSubjectPostImportReport: { checkedSceneCount: 0, missingSceneCount: 0, missingItemCount: (sceneImportReport?.createdSubjectItems?.length || 0) + (sceneImportReport?.skippedSubjectItems?.length || 0), missingSceneReports: [], supplementReport: { createdItems: sceneImportReport?.createdSubjectItems || [], skippedItems: sceneImportReport?.skippedSubjectItems || [], failedItems: [], countsByType: { character: 0, prop: 0, environment: 0 } }, importedSubjectCounts: sceneImportReport?.importedSubjectCounts || { character: 0, prop: 0, environment: 0 } },
                                    dbRunInsertedCounts: sceneImportReport?.dbRunInsertedCounts,
                                    dbPersistedCounts: sceneImportReport?.dbPersistedCounts,
                                    importedSubjectCounts: prevImport.importedSubjectCounts ? {
                                        character: (prevImport.importedSubjectCounts.character || 0) + (sceneImportReport?.importedSubjectCounts?.character || 0),
                                        prop: (prevImport.importedSubjectCounts.prop || 0) + (sceneImportReport?.importedSubjectCounts?.prop || 0),
                                        environment: (prevImport.importedSubjectCounts.environment || 0) + (sceneImportReport?.importedSubjectCounts?.environment || 0),
                                    } : sceneImportReport?.importedSubjectCounts,
                                }
                            };
                        });
                        
                        const createdCount = sceneImportReport?.createdSubjectItems?.length || 0;
                        const skippedCount = sceneImportReport?.skippedSubjectItems?.length || 0;
                        setAnalysisFlowStatus({
                            phase: 'completed',
                            message: t(\`🎉 第二阶段(资产生成)恢复成功！自动补充了 \${createdCount} 个资产 (跳过 \${skippedCount} 个)。\`, \`Phase 2 recovered successfully! Created \${createdCount} assets (skipped \${skippedCount}).\`)
                        });
                    }
                } else {
                    setAnalysisFlowStatus({ phase: 'warning', message: t('恢复第二阶段分析失败：未返回有效内容', 'Failed to resume phase 2: returned no content') });
                }
                clearAnalysisTaskMarker(activeEpisode.id);
            } catch (e) {
                console.error("Phase 2 recovery error:", e);
                setAnalysisFlowStatus({ phase: 'failed', message: t(\`恢复第二阶段分析任务失败：\${e?.message || e}\`, \`Failed to resume Phase 2 analysis task: \${e?.message || e}\`) });
                clearAnalysisTaskMarker(activeEpisode.id);
            } finally {
                analysisResumeInFlightRef.current = false;
                setIsRetryingPhase2(false);
                setActiveAnalysisTaskId('');
            }
            return;
        }
`;

content = content.replace(hookStartRegex, hookStart + "\n" + phase2Injection);
fs.writeFileSync(filePath, content);
console.log("Injected via modified regex");
