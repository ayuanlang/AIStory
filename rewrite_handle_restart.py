import re
import sys

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

replacement_code = """
            const stage2_1Text = extractAnalysisTextFromResult(stage2_1Result) || '';
            globalStage2_1Text = stage2_1Text;
            if (onLog) onLog('Stage 2.1 completed. Kicking off Stage 2.2 (Beats) and Stage 3 (Asset Design) concurrently for restart...', 'info');

            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('📝 正在并发执行：生成镜头节拍与资产细设...', 'Concurrently running Scene Beats and Asset Design...'),
            });

            const runStage2_2Task = async () => {
                const stage2_2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md');
                const stage2_2UserInput = `${stage2UserInput}\\n\\n### 【上游提取的资产清单 Subject Index】\\n${stage2_1Text}`;
                const stage2_2ResultObj = await awaitAnalyzeSceneWithRecovery(
                    () => analyzeScene(
                        stage2_2UserInput,
                        stage2_2PromptRes?.content || '',
                        null,
                        null,
                        analysisAttentionNotes,
                        selectedReuseSubjectAssets,
                        {
                            onTaskCreated: (taskId) => {
                                setActiveAnalysisTaskId(String(taskId || '').trim());
                                saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 3 });
                            },
                        },
                        projectId
                    ),
                    { startedAt, baselineText: stage2_1Text }
                );
                return { 
                    stage2_2Text: extractAnalysisTextFromResult(stage2_2ResultObj) || '',
                    stage2_2Result: stage2_2ResultObj
                };
            };

            const runStage3Task = async () => {
                try {
                    return await runPostImportSceneSubjectPipeline(null, null, {
                        explicitSubjectIndexText: globalStage2_1Text || stage2_1Text
                    });
                } catch (e) {
                    if (onLog) onLog(`Stage 3 background execution failed: ${e?.message || e}`, 'error');
                    return null;
                }
            };

            const [beatsOutcome, assetsOutcome] = await Promise.allSettled([
                runStage2_2Task(),
                runStage3Task()
            ]);

            if (beatsOutcome.status !== 'fulfilled') {
                throw beatsOutcome.reason;
            }

            const { stage2_2Text, stage2_2Result } = beatsOutcome.value;
            const postImportSceneSubjectReport = assetsOutcome.status === 'fulfilled' ? assetsOutcome.value : null;

            const stage2Text = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\\n\\n');
            const finalAnalysisText = [String(stage1SourceText || '').trim(), stage2Text].filter(Boolean).join('\\n\\n');
            
            const stage2Result = {
                ...(stage2_1Result || {}),
                ...(stage2_2Result || {}),
                meta: stage2_2Result?.meta || stage2_1Result?.meta,
                subjects_json: stage2_1Result?.subjects_json || stage2_2Result?.subjects_json,
            };

            const analysisSections = extractAnalysisSections(finalAnalysisText);
            if (!analysisSections.hasStructuredSubjectIndex) {
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            setLlmRawResultContent(finalAnalysisText);
            setLlmResultContent(normalizeLlmMarkdownTable(finalAnalysisText));
            lastLoadedAnalysisRef.current = finalAnalysisText;

            if (stage2Result?.meta) {
                runtimeMeta = extractAnalysisRuntimeMeta(stage2Result.meta);
                setAnalysisRuntimeMeta(runtimeMeta);
            }

            await persistLlmResultContent(finalAnalysisText, 'ai_scene_analysis_result', {
                source: 'restart-stage2',
                stage1RawText: stage1SourceText,
                stage2RawText: stage2Text,
            });

            importReport = await runAutoImportAndSwitchToScenes(finalAnalysisText, {
                switchToScenes: false,
                importOptions: {
                    autoSupplementSceneSubjects: false,
                    suppressAlerts: true,
                    subjectsJson: stage2Result?.subjects_json || null,
                },
            });
            importReport = await ensureSubjectsImportedBeforePostChecks(stage2Result, importReport);
            maybeAlertIncompleteSubjectsImport(stage2Result, finalAnalysisText);

            if (importReport && typeof importReport === 'object' && postImportSceneSubjectReport) {
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
            }

            setAnalysisUiReport({
"""

start_str = "const stage2_1Text = extractAnalysisTextFromResult(stage2_1Result) || '';\n            globalStage2_1Text = stage2_1Text;\n            if (onLog) onLog('Stage 2.1 completed, starting Stage 2.2 (Beats)...', 'info');"
end_str = "setAnalysisUiReport({"

start_idx = text.find(start_str)
end_idx = text.find(end_str, start_idx)

if start_idx == -1 or end_idx == -1:
    print("Could not find the target block boundaries in handleRestartStage2!")
    sys.exit(1)

new_text = text[:start_idx] + replacement_code.strip() + "\n            " + text[end_idx + len(end_str):]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Successfully replaced execution block in handleRestartStage2.")
