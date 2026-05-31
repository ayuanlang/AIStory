import re
import sys

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    original_text = f.read()

# Define the replacement block
replacement_code = """
                if (onLog) onLog('Stage 2.1 completed. Kicking off Stage 2.2 (Beats Generation) and Stage 3 (Asset Design) concurrently...', 'info');

                setAnalysisFlowStatus({
                    phase: 'scene_beats',
                    message: t('📝 正在并发执行：生成镜头节拍与资产细设...', 'Concurrently running Scene Beats and Asset Design...'),
                });

                const runStage2_2Task = async () => {
                    const stage2_2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md');
                    let finalStage2_2Prompt = stage2_2PromptRes?.content || '';
                    let finalStage2_2UserInput = `${stage2UserInput}\\n\\n### 【上游提取的资产清单 Subject Index】\\n${stage2_1Text}`;

                    if (isSuperuser || isSuperuserRef.current) {
                        setAnalysisModalMode('stage2');
                        setSystemPrompt(finalStage2_2Prompt);
                        setUserPrompt(finalStage2_2UserInput);
                        setShowAnalysisModal(true);
                        if (onLog) onLog('Superuser Stage 2.2 submit: prompt preview opened before submission.', 'info');

                        const confirmedStage2_2 = await new Promise(resolve => {
                            phase2ResolverRef.current = resolve;
                        });

                        if (!confirmedStage2_2 || typeof confirmedStage2_2 !== 'object') {
                            throw new Error('Superuser canceled Stage 2.2 prompt confirmation.');
                        }

                        finalStage2_2Prompt = confirmedStage2_2.systemPrompt || finalStage2_2Prompt;
                        finalStage2_2UserInput = confirmedStage2_2.userPrompt || finalStage2_2UserInput;
                    }

                    const stage2_2ResultObj = await awaitAnalyzeSceneWithRecovery(
                        () => analyzeScene(
                            finalStage2_2UserInput,
                            finalStage2_2Prompt,
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
                        { startedAt: phaseMarks.llmReturnedAt || startedAt, baselineText: stage2_1Text }
                    );

                    const text2_2 = extractAnalysisTextFromResult(stage2_2ResultObj) || '';
                    
                    let isUpstreamError2 = false;
                    let errMsg2 = '';
                    const matchObjStr2 = text2_2.trim().replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/, '');
                    if (matchObjStr2.startsWith('{')) {
                        try {
                            const parseObj = JSON.parse(matchObjStr2);
                            if (parseObj.code === 500 || parseObj.error || parseObj.msg) {
                                isUpstreamError2 = true;
                                errMsg2 = `上游接口异常 (Stage 2.2)：${parseObj.msg || parseObj.error?.message || matchObjStr2}`;
                            }
                        } catch(e) {}
                    }
                    if (!isUpstreamError2 && /服务器错误|maintained|too many requests|rate limit/i.test(text2_2)) {
                        isUpstreamError2 = true;
                        errMsg2 = `上游接口熔断或系统维护 (Stage 2.2)：${text2_2.slice(0, 100)}`;
                    }
                    if (isUpstreamError2) {
                        throw new Error(errMsg2);
                    }
                    if (!String(text2_2).trim() || !text2_2.includes("|")) {
                        throw new Error('Stage 2.2 镜头节拍生成失败：未检测到有效的分镜表格产出，请重试。');
                    }
                    
                    return { stage2_2Text: text2_2, stage2_2Result: stage2_2ResultObj };
                };

                const runStage3Task = async () => {
                    if (!autoStartSubjectAnalysis) return null;
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
                    throw beatsOutcome.reason; // Let the caller catch block handle Beats generation failure
                }

                const { stage2_2Text, stage2_2Result } = beatsOutcome.value;
                postImportSceneSubjectReport = assetsOutcome.status === 'fulfilled' ? assetsOutcome.value : null;

                stage2PhaseRawText = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\\n\\n');
                finalAnalysisText = [String(analyzedText || '').trim(), stage2PhaseRawText].filter(Boolean).join('\\n\\n');

                importSourceText = finalAnalysisText;
                phaseMarks.persistStartedAt = Date.now();
                
                try {
                    if (onLog) onLog('Persisting split-flow combined raw LLM output immediately after Beats return...', 'process');
                    await persistLlmResultContent(finalAnalysisText || '', 'ai_scene_analysis_result', {
                        source: 'advanced-analysis-split-combined-immediate',
                        stage1RawText: stage1PhaseRawText,
                        stage2RawText: stage2PhaseRawText,
                        stage2_1Text: globalStage2_1Text,
                    });
                    finalRawResultPersistedEarly = true;
                } catch (persistErr) {
                    if (onLog) onLog(`Immediate split-flow raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                } finally {
                    phaseMarks.persistFinishedAt = Date.now();
                }

                analysisSections = extractAnalysisSections(stage2PhaseRawText);
                analysisSections.hasStructuredSubjectIndex = true;
                analysisSections.subjectIndexText = String(stage2_1Text || '').trim();
            }

            if (!analysisSections.hasStructuredSubjectIndex) {
                if (onLog) onLog('Missing asset index after Stage 2 output validation. Skipping auto-import and triggering cleanup retry.', 'warning');
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            setLlmRawResultContent(finalAnalysisText || '');
            setLlmResultContent(normalizeLlmMarkdownTable(finalAnalysisText || ''));
            lastLoadedAnalysisRef.current = finalAnalysisText || '';

            try {
                if (true || !savedByBackend && !finalRawResultPersistedEarly) {
                    phaseMarks.persistStartedAt = Date.now();
                    if (onLog) onLog('Saving advanced raw LLM output to episode analysis field...', 'process');
                    await persistLlmResultContent(finalAnalysisText || '', 'ai_scene_analysis_result', {
                        source: splitStage1Flow ? 'advanced-analysis-split-combined' : 'advanced-analysis',
                        stage1RawText: stage1PhaseRawText,
                        stage2RawText: stage2PhaseRawText,
                        stage2_1Text: globalStage2_1Text || undefined,
                    });
                } else {
                    if (savedByBackend) {
                        phaseMarks.persistStartedAt = phaseMarks.persistStartedAt || Date.now();
                    }
                    if (onLog) onLog('Advanced LLM raw output already saved by backend. Refreshing local episode cache...', 'info');
                    if (onUpdateEpisodeInfo && activeEpisode?.id) {
                        await onUpdateEpisodeInfo(activeEpisode.id, {
                            ai_stage_outputs: JSON.stringify(buildStageOutputsObject({
                                analysisRawText: finalAnalysisText || analyzedText || '',
                                assetRawText: activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                            }), null, 2),
                        });
                    }
                }
            } catch (persistErr) {
                if (onLog) onLog(`Advanced raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }

            phaseMarks.importStartedAt = Date.now();
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('📝 分析框架解构完毕，正在导入您的工作区...', 'Importing Markdown into workspace...'),
            });
            try {
                importReport = await runAutoImportAndSwitchToScenes(importSourceText || finalAnalysisText || '', {
                    switchToScenes: false,
                    importOptions: {
                        autoSupplementSceneSubjects: false,
                        suppressAlerts: true,
                        subjectsJson: result?.subjects_json || null,
                    },
                });
                if (!importReport) {
                    importWarningMessage = t('自动导入未返回结果，请检查导入配置或返回格式。', 'Auto-import returned no result.');
                    setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
                }
            } catch (importErr) {
                importWarningMessage = t(`自动导入失败：${importErr?.message || importErr}`, `Auto-import failed: ${importErr?.message || importErr}`);
                if (onLog) onLog(`Auto-import failed (checks will continue): ${importErr?.message || importErr}`, 'warning');
                setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            importReport = await ensureSubjectsImportedBeforePostChecks(result, importReport);
            maybeAlertIncompleteSubjectsImport(result, finalAnalysisText || '');

            if (importReport && typeof importReport === 'object' && postImportSceneSubjectReport) {
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.dbRunInsertedCounts) importReport.dbRunInsertedCounts = postImportSceneSubjectReport.dbRunInsertedCounts;
                if (postImportSceneSubjectReport?.dbPersistedCounts) importReport.dbPersistedCounts = postImportSceneSubjectReport.dbPersistedCounts;
                if (postImportSceneSubjectReport?.importedSubjectCounts) {
                    importReport.importedSubjectCounts = {
                        character: (importReport.importedSubjectCounts?.character || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.character) || 0),
                        prop: (importReport.importedSubjectCounts?.prop || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.prop) || 0),
                        environment: (importReport.importedSubjectCounts?.environment || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.environment) || 0),
                        poster: (importReport.importedSubjectCounts?.poster || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.poster) || 0),
                    };
                }
            }
"""

start_str = "if (onLog) onLog('Stage 2.1 completed. Now starting Stage 2.2 (Beats Generation)...', 'info');"
end_str = "let firstPassReport = null;"

start_idx = original_text.find(start_str)
end_idx = original_text.find(end_str, start_idx)

if start_idx == -1 or end_idx == -1:
    print("Could not find the target block boundaries!")
    sys.exit(1)

new_text = original_text[:start_idx] + replacement_code.strip() + "\n\n            " + original_text[end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Successfully replaced the execution block with concurrent Promise.allSettled logic.")
