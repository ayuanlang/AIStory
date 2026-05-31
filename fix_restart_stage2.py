import re

with open('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# The robust version of runStage2_2Task
robust_task = """            const runStage2_2Task = async () => { 
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
                    { startedAt, baselineText: stage2_1Text } 
                ); 

                const text2_2 = extractAnalysisTextFromResult(stage2_2ResultObj) || ''; 
                 
                let isUpstreamError2 = false; 
                let errMsg2 = ''; 
                const matchObjStr2 = text2_2.trim().replace(/^```(?:json)?\s*/i, '').replace(/\\s*```$/, ''); 
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
                    throw new Error('Stage 2.2 镜头节拍生成失败：未检测到有效的分镜表格产出，请重试。\\n' + text2_2.slice(0, 200)); 
                } 
                
                return { stage2_2Text: text2_2, stage2_2Result: stage2_2ResultObj }; 
            };"""

old_task_pattern = re.compile(
    r"const runStage2_2Task = async \(\) => \{\s+const stage2_2PromptRes = await fetchPrompt\('skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation\.md'\);\s+const stage2_2UserInput = `\$\{stage2UserInput\}\\n\\n### 【上游提取的资产清单 Subject Index】\\n\$\{stage2_1Text\}`;\s+const stage2_2ResultObj = await awaitAnalyzeSceneWithRecovery\([\s\S]*?return \{\s*stage2_2Text: extractAnalysisTextFromResult\(stage2_2ResultObj\) \|\| '',\s+stage2_2Result: stage2_2ResultObj\s+\};\s+\};"
)

new_text = old_task_pattern.sub(robust_task, text)

# Just to be sure, check if the replacement happened
if new_text != text:
    with open('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Replaced runStage2_2Task in handleRestartStage2 successfully.")
else:
    print("Failed to replace. Pattern not found.")
