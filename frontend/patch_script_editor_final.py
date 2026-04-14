import re, codecs

def patch():
    filepath = 'C:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
    with codecs.open(filepath, 'r', 'utf-8') as f:
        text = f.read()

    # 1. add state
    if 'setLlmAssetRawResultContent' not in text:
        text = text.replace(
            "const [llmRawResultContent, setLlmRawResultContent] = useState('');",
            "const [llmRawResultContent, setLlmRawResultContent] = useState('');\n    const [llmAssetRawResultContent, setLlmAssetRawResultContent] = useState('');"
        )
    
    # 2. replace prompts
    text = text.replace("'subject_generation.txt'", "'skills/scene_analysis_feature_stack/entity_design.md'")
    text = text.replace("'scene_analysis.txt'", "'skills/scene_analysis_feature_stack/scene_planning.md'")

    # 3. Add 'subject_generation' function name flag to analyzeScene in the main flow
    target_block = '''analyzeScene(
                sceneTextContent,
                promptContent,
                null,
                activeEpisode?.id || null,
                analysisAttentionNotes,
                selectedReuseSubjectAssets,
                null,
                projectId
            );'''
    repl_block = '''analyzeScene(
                sceneTextContent,
                promptContent,
                null,
                activeEpisode?.id || null,
                analysisAttentionNotes,
                selectedReuseSubjectAssets,
                null,
                projectId,
                "subject_generation"
            );'''
    text = text.replace(target_block, repl_block)

    # 4. Modify 'saving_scenes' message 
    text = text.replace("phase: 'importing',", "phase: 'saving_scenes',")

    # 5. Move selectedReuseSubjectAssets up before runPostImportSceneSubjectPipeline
    # and rewrite runPostImportSceneSubjectPipeline
    
    p1 = text.find('const runPostImportSceneSubjectPipeline = useCallback(')
    p2 = text.find('}, [onLog, projectId, t]);\n\n    const parseMarkdownTable', p1)
    
    p3 = text.find('const selectedReuseSubjectAssets = useMemo(() => {')
    p4 = text.find('}, [availableSubjectAssets, selectedReuseSubjectIds]);', p3)

    if p1 != -1 and p3 != -1 and p3 > p2:
        # It's currently below. We need to extract the selectedReuseSubjectAssets 
        # and move it ABOVE runPostImport...
        sel_block = text[p3:p4+len('}, [availableSubjectAssets, selectedReuseSubjectIds]);')]
        text = text[:p3] + text[p3+len(sel_block):]
        
        # also runPostImport block
        pipeline_block = text[p1:p2+len('}, [onLog, projectId, t]);')]
        
        # build the new pipeline block
        new_pipeline = '''const runPostImportSceneSubjectPipeline = useCallback(async (importReport, options = {}) => {
        const importedSceneRows = Array.isArray(importReport?.importedSceneRows) ? importReport.importedSceneRows : [];
        const emptyReport = {
            checkedSceneCount: importedSceneRows.length,
            missingSceneCount: 0,
            missingItemCount: 0,
            missingSceneReports: [],
            supplementReport: {
                createdItems: [], skippedItems: [], failedItems: [], sceneReports: [],
                countsByType: { character: 0, prop: 0, environment: 0 },
            },
        };

        if (!projectId || importedSceneRows.length === 0) {
            return emptyReport;
        }

        const authoritativeSubjectText = llmRawResultContent || llmResultContent || activeEpisode?.ai_scene_analysis_result || '';
        let subjectIndexText = "";

        onLog?.([Asset Gen Tracking] Initial authoritativeText length: , "info");

        const match = authoritativeSubjectText.match(/(?:###?|##)\\s*(?:Subject Index|角色|道具|场景|设计资产|Entities)[\\s\\S]*/i);
        if (match) {
            subjectIndexText = match[0];
            onLog?.([Asset Gen Tracking] Extracted Subject Index (length: ), "success");
        } else {
            subjectIndexText = authoritativeSubjectText;
            onLog?.([Asset Gen Tracking] Failed to find Subject Index header! Using fallback full text for asset generation., "warning");
        }

        if (!subjectIndexText.trim()) {
            onLog?.("No Subject Index found in the analysis result. Skipping asset generation.", "warning");
            return emptyReport;
        }

        setAnalysisFlowStatus({
            phase: "generating_assets",
            message: t("正在根据 Subject Index 生成设计资产...", "Generating design assets from Subject Index..."),
        });

        try {
            onLog?.([Asset Gen Tracking] Preparing to fetch 'entity_design.md', "info");
            const promptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design.md").catch(() => null);
            const promptContent = promptRes?.content || "";
            if (!promptContent) {
                onLog?.([Asset Gen Tracking] Warning: 'entity_design.md' prompt is empty or failed to load., "warning");
            }

            onLog?.([Asset Gen Tracking] Launching second LLM call for 'subject_generation', "process");

            const result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    subjectIndexText,
                    promptContent,
                    null,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    null,
                    projectId,
                    "subject_generation"
                ),
                { startedAt: Date.now(), baselineText: "" }
            );

            const analyzedText = extractAnalysisTextFromResult(result);        
            setLlmAssetRawResultContent(analyzedText);

            if (analyzedText) {
                // Automatically import the generated subjects
                const sceneImportReport = await doImportText(analyzedText, false, {
                    onLog,
                    projectId,
                    episodeId: activeEpisode?.id,
                });
                onLog?.([Asset Gen Tracking] Asset import completed. Created: , Matched: , "success");
            }

        } catch (error) {
            console.error("Asset generation step failed:", error);
            onLog?.(Asset generation failed: , "error");
        }

        return emptyReport;
    }, [
        projectId, llmRawResultContent, llmResultContent, activeEpisode, t, onLog,
        fetchPrompt, analyzeScene, awaitAnalyzeSceneWithRecovery,
        analysisAttentionNotes, selectedReuseSubjectAssets, extractAnalysisTextFromResult, doImportText
    ]);'''
        
        # Now replace both
        new_text = text[:p1] + sel_block + '\n\n    ' + new_pipeline + text[p1 + len(pipeline_block):]
        text = new_text

    # 6. Add UI section for second text area
    ui_find = '''                        label={t('原始结果数据', 'Raw Result Content')}
                        value={llmRawResultContent}'''
                        
    if 'llmAssetRawResultContent' not in ui_find and 'llmAssetRawResultContent' not in text.split('label={t(\'原始结果数据\', \'Raw Result Content\')}')[1]:
        ui_replace = '''                        label={t('剧本结构解析数据 (第一次大模型调用)', 'Scene Analysis Raw Content')}
                        value={llmRawResultContent}
                        onChange={setLlmRawResultContent}
                        disabled={isRunningAnalysis}
                    />
                </div>
                
                <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                    <TextArea
                        label={t('资产生成结果数据 (第二次大模型调用)', 'Asset Generation Raw Content')}
                        value={llmAssetRawResultContent}
                        onChange={setLlmAssetRawResultContent}
                        disabled={isRunningAnalysis}
                    />
                </div>
                
                <div style={{ flex: 1, display: 'none' }}>
                    <TextArea
                        label={t('Old raw content', 'old')}
                        value={llmRawResultContent}'''
        text = text.replace(ui_find, ui_replace)

    with codecs.open(filepath, 'w', 'utf-8') as f:
        f.write(text)
    
patch()
print("Success Repair")
