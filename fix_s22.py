import sys

f = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
txt = open(f, 'r', encoding='utf-8').read()

old = """                const stage2_2ResultObj = await awaitAnalyzeSceneWithRecovery( 
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
                );"""

new_val = """                const stage2_2ResultObj = await analyzeScene( 
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
                    projectId,
                    'script_analysis_stage_2_2_beats'
                );"""

old = txt[txt.find('const runStage2_2Task = async', txt.find('const runStage2_2Task = async')+1):]
idx_start = old.find('const stage2_2ResultObj = await awaitAnalyzeSceneWithRecovery(')
idx_end = old.find(');', idx_start) + 2

old_exact = old[idx_start:idx_end]

txt = txt.replace(old_exact, new_val)
open(f, 'w', encoding='utf-8').write(txt)
