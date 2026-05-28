import sys
import re

file_path = r"c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace main flow
target_1 = """                const stage2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_beats_and_assets.md');
                let finalStage2Prompt = stage2PromptRes?.content || '';
                let finalStage2UserInput = stage2UserInput;

                if (isSuperuser || isSuperuserRef.current) {
                    setAnalysisModalMode('stage2');
                    setSystemPrompt(finalStage2Prompt);
                    setUserPrompt(finalStage2UserInput);
                    setShowAnalysisModal(true);
                    if (onLog) onLog('Superuser Stage 2 submit: prompt preview opened before submission.', 'info');

                    const confirmedStage2 = await new Promise(resolve => {
                        phase2ResolverRef.current = resolve;
                    });

                    if (!confirmedStage2 || typeof confirmedStage2 !== 'object') {
                        throw new Error('Superuser canceled Stage 2 prompt confirmation.');
                    }

                    finalStage2Prompt = confirmedStage2.systemPrompt || finalStage2Prompt;
                    finalStage2UserInput = confirmedStage2.userPrompt || finalStage2UserInput;
                }

                const stage2Result = await awaitAnalyzeSceneWithRecovery(
                    () => analyzeScene(
                        finalStage2UserInput,
                        finalStage2Prompt,
                        null,
                        null,
                        analysisAttentionNotes,
                        selectedReuseSubjectAssets,
                        {
                            onTaskCreated: (taskId) => {
                                setActiveAnalysisTaskId(String(taskId || '').trim());
                                saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 2 });
                            },
                        },
                        projectId
                    ),
                    { startedAt: phaseMarks.llmReturnedAt || startedAt, baselineText: '' }
                );

                const stage2Text = extractAnalysisTextFromResult(stage2Result) || '';
                stage2PhaseRawText = String(stage2Text || '').trim();
                finalAnalysisText = [String(analyzedText || '').trim(), String(stage2Text || '').trim()].filter(Boolean).join('\\n\\n');"""

replacement_1 = """                const stage2_1PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_1_assets_extraction.md');
                let finalStage2_1Prompt = stage2_1PromptRes?.content || '';
                let finalStage2_1UserInput = stage2UserInput;

                if (isSuperuser || isSuperuserRef.current) {
                    setAnalysisModalMode('stage2');
                    setSystemPrompt(finalStage2_1Prompt);
                    setUserPrompt(finalStage2_1UserInput);
                    setShowAnalysisModal(true);
                    if (onLog) onLog('Superuser Stage 2.1 submit: prompt preview opened before submission.', 'info');

                    const confirmedStage2_1 = await new Promise(resolve => {
                        phase2ResolverRef.current = resolve;
                    });

                    if (!confirmedStage2_1 || typeof confirmedStage2_1 !== 'object') {
                        throw new Error('Superuser canceled Stage 2.1 prompt confirmation.');
                    }

                    finalStage2_1Prompt = confirmedStage2_1.systemPrompt || finalStage2_1Prompt;
                    finalStage2_1UserInput = confirmedStage2_1.userPrompt || finalStage2_1UserInput;
                }
                
                if (onLog) onLog('Submitting Stage 2.1 (Asset Extraction)...', 'info');

                const stage2_1Result = await awaitAnalyzeSceneWithRecovery(
                    () => analyzeScene(
                        finalStage2_1UserInput,
                        finalStage2_1Prompt,
                        null,
                        null,
                        analysisAttentionNotes,
                        selectedReuseSubjectAssets,
                        {
                            onTaskCreated: (taskId) => {
                                setActiveAnalysisTaskId(String(taskId || '').trim());
                                saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 2 });
                            },
                        },
                        projectId
                    ),
                    { startedAt: phaseMarks.llmReturnedAt || startedAt, baselineText: '' }
                );

                const stage2_1Text = extractAnalysisTextFromResult(stage2_1Result) || '';
                if (onLog) onLog('Stage 2.1 completed. Now starting Stage 2.2 (Beats Generation)...', 'info');

                const stage2_2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md');
                let finalStage2_2Prompt = stage2_2PromptRes?.content || '';
                let finalStage2_2UserInput = `${stage2UserInput}\\n\\n### 銆愪笂娓告彁鍙栫殑璧勪骇娓呭崟 Subject Index銆慭\n${stage2_1Text}`;

                if (isSuperuser || isSuperuserRef.current) {
                    // Re-use logic for stage 2.2 preview
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

                const stage2_2Result = await awaitAnalyzeSceneWithRecovery(
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
                    { startedAt: phaseMarks.llmReturnedAt || startedAt, baselineText: '' }
                );

                const stage2_2Text = extractAnalysisTextFromResult(stage2_2Result) || '';
                
                stage2PhaseRawText = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\\n\\n');
                finalAnalysisText = [String(analyzedText || '').trim(), stage2PhaseRawText].filter(Boolean).join('\\n\\n');
"""

text = text.replace(target_1, replacement_1)

target_2 = """            const stage2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_beats_and_assets.md');
            const stage2Result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    stage2UserInput,
                    stage2PromptRes?.content || '',
                    null,
                    null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            setActiveAnalysisTaskId(String(taskId || '').trim());
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 2 });
                        },
                    },
                    projectId
                ),
                { startedAt, baselineText: String(activeEpisode?.ai_scene_analysis_result || '').trim() }
            );

            const stage2Text = extractAnalysisTextFromResult(stage2Result) || '';
            const finalAnalysisText = [String(stage1SourceText || '').trim(), String(stage2Text || '').trim()].filter(Boolean).join('\\n\\n');"""

replacement_2 = """            const stage2_1PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_1_assets_extraction.md');
            if (onLog) onLog('Restarting Stage 2.1 (Asset Extraction)...', 'info');
            const stage2_1Result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    stage2UserInput,
                    stage2_1PromptRes?.content || '',
                    null,
                    null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            setActiveAnalysisTaskId(String(taskId || '').trim());
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 2 });
                        },
                    },
                    projectId
                ),
                { startedAt, baselineText: String(activeEpisode?.ai_scene_analysis_result || '').trim() }
            );

            const stage2_1Text = extractAnalysisTextFromResult(stage2_1Result) || '';
            if (onLog) onLog('Stage 2.1 completed, starting Stage 2.2 (Beats)...', 'info');

            const stage2_2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md');
            const stage2_2UserInput = `${stage2UserInput}\\n\\n### 銆愪笂娓告彁鍙栫殑璧勪骇娓呭崟 Subject Index銆慭\n${stage2_1Text}`;
            
            const stage2_2Result = await awaitAnalyzeSceneWithRecovery(
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
                { startedAt, baselineText: String(activeEpisode?.ai_scene_analysis_result || '').trim() }
            );
            
            const stage2_2Text = extractAnalysisTextFromResult(stage2_2Result) || '';
            
            // To emulate 'stage2Text' that gets saved, we combine them
            const stage2Text = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\\n\\n');
            const finalAnalysisText = [String(stage1SourceText || '').trim(), stage2Text].filter(Boolean).join('\\n\\n');"""

text = text.replace(target_2, replacement_2)

# Save
with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Done. Replaced occurrences.")
