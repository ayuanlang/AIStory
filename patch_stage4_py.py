import re

with open("frontend/src/pages/editor/components/ScriptEditor.jsx", "r", encoding="utf-8") as f:
    text = f.read()

# Fix missed phases
text = re.sub(r"phase:\s*['\"]generating_assets['\"]", "phase: 'assets_gen'", text)
text = re.sub(r"phase:\s*['\"]autosaving['\"]", "phase: 'script_opt'", text)
text = re.sub(r"phase:\s*['\"]analyzing['\"]", "phase: 'script_opt'", text)
text = re.sub(r"phase:\s*['\"]processing_output_workspace['\"]", "phase: 'completed'", text)
text = re.sub(r"phase:\s*['\"]saving_scenes['\"]", "phase: 'scene_beats'", text)

# Now apply Stage 4 progress tracking mapping
pattern = r"setAnalysisFlowStatus\(\{\n\s*phase:\s*\"assets_gen\",\n\s*message:\s*t\(\"✨ 正在执行第三阶段资产设计\.\.\.\",\s*\"Running Stage 3 asset design from the Stage 2 asset index\.\.\.\"\),\n\s*\}\);\n\n\s*try\s*\{\n\s*onLog\?\.\(`\[Stage 3 Asset Design\] Preparing to fetch 4 entity_design prompts`\);\s*const promptFiles = \[\s*\{ key: 'characters', path: 'skills/scene_analysis_feature_stack/entity_design_character\.md' \},\s*\{ key: 'environments', path: 'skills/scene_analysis_feature_stack/entity_design_environment\.md' \},\s*\{ key: 'props', path: 'skills/scene_analysis_feature_stack/entity_design_prop\.md' \},\s*\{ key: 'posters', path: 'skills/scene_analysis_feature_stack/entity_design_poster\.md' \}\s*\]\.filter\(p => !options\.targetEntityTypes \|\| options\.targetEntityTypes\.includes\(p\.key\)\);\s*const commonPromptRes = await fetchPrompt\(\"skills/scene_analysis_feature_stack/entity_design_common\.md\"\)\.catch\(\(\) => null\);\s*const commonPromptContent = commonPromptRes\?\.content \|\| \"\";\s*const promptsData = await Promise\.all\(\s*promptFiles\.map\(async p => \(\{\s*\.\.\.p,\s*content: commonPromptContent \+ \"\\n\\n\" \+ \(\(await fetchPrompt\(p\.path\)\.catch\(\(\) => null\)\)\?\.content \|\| \"\"\)\s*\}\)\)\s*\);\s*let finalSubjectIndexText = subjectIndexText;\s*// Hotfix.*?\}\)\s*\)\.then\(res => \(\{ key: pData\.key, result: res \}\)\);\s*\}\)\s*\);"

new_block = """setAnalysisFlowStatus({
            phase: "assets_gen",
            message: t("✨ 正在执行第四阶段资产生成 (共 4 项并发推演...)", "Running Stage 4 asset design..."),
        });

        try {
            onLog?.(`[Stage 3 Asset Design] Preparing to fetch 4 entity_design prompts`);
            
            const promptFiles = [
                { key: 'characters', path: 'skills/scene_analysis_feature_stack/entity_design_character.md' },
                { key: 'environments', path: 'skills/scene_analysis_feature_stack/entity_design_environment.md' },
                { key: 'props', path: 'skills/scene_analysis_feature_stack/entity_design_prop.md' },
                { key: 'posters', path: 'skills/scene_analysis_feature_stack/entity_design_poster.md' }
            ].filter(p => !options.targetEntityTypes || options.targetEntityTypes.includes(p.key));

            const commonPromptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design_common.md").catch(() => null);
            const commonPromptContent = commonPromptRes?.content || "";

            const promptsData = await Promise.all(
                promptFiles.map(async p => ({
                    ...p,
                    content: commonPromptContent + "\\n\\n" + ((await fetchPrompt(p.path).catch(() => null))?.content || "")
                }))
            );

            let finalSubjectIndexText = subjectIndexText;
            // Hotfix: Ensure any trailing Scenes markdown that accidentally leaked into the Subject Index gets cleanly removed
            const scenesOftMatch = finalSubjectIndexText.match(/(?:^|\\n)\\s*(?:###?\\s*(?:-1\\)\\s*类型研判|Scenes|场景列表))/i);
            if (scenesOftMatch && scenesOftMatch.index >= 0) {
                finalSubjectIndexText = finalSubjectIndexText.slice(0, scenesOftMatch.index).trim();
            }
            
            const designProjectContextSection = buildStage1ProjectContextSection()
                .replace('Project Context (prepend and treat as high-priority constraints):', 'Project Context (prepend and treat as high-priority constraints for generating design assets):')
                .replace('Use this project context as first-class constraints before analyzing the script.', 'Use this project context as first-class constraints before generating the subjects.');

            if (designProjectContextSection) {
                finalSubjectIndexText = `${designProjectContextSection}\\n\\n[第二阶段资产清单 - 第三阶段权威输入]\\n${finalSubjectIndexText}`;
            }

            const isUserSuper = isSuperuser || isSuperuserRef.current;
            if (isUserSuper) {
                setAnalysisModalMode('stage3');
                setSystemPrompt(promptsData[0].content); // Show character one as representative
                setUserPrompt(finalSubjectIndexText);
                setShowAnalysisModal(true);
                
                onLog?.(`[Stage 3 Asset Design] Waiting for superuser to confirm the asset-design prompt...`);
                // Wait for the modal submit
                const confirmed = await new Promise(resolve => {
                    phase2ResolverRef.current = resolve;
                });
                
                if (!confirmed || typeof confirmed !== 'object') {
                    onLog?.(`[Stage 3 Asset Design] Superuser aborted the asset-design stage.`);
                    return emptyReport;
                }
                
                promptsData[0].content = confirmed.systemPrompt || promptsData[0].content;
                finalSubjectIndexText = confirmed.userPrompt || finalSubjectIndexText;
            }

            onLog?.('[Stage 3 Asset Design] Launching 4 parallel asset-design LLM calls...');

            const phase1SystemApiId = Number(functionApiConfigs?.selectedApi?.system_api_id || 0)
                || Number(localStorage.getItem('func_api_script_analysis') || 0)
                || null;
            if (phase1SystemApiId) {
                onLog?.(`[Stage 3 Asset Design] Reusing Stage 1 system_api_id=${phase1SystemApiId} for script_analysis routing.`, 'info');
            } else {
                onLog?.('[Stage 3 Asset Design] Stage 1 system_api_id is missing; fallback routing may select a different API.', 'warning');
            }

            const phase2StartedAt = Date.now();
            let assetsGenCompletedCount = 0;
            const targetAssetsCount = promptsData.length;

            // Run them concurrently
            const results = await Promise.allSettled(
                promptsData.map(async (pData, index) => {
                    const isPrimary = index === 0;

                    let specificSubjectIndexText = finalSubjectIndexText;
                    
                    // Strip LLM think blocks
                    specificSubjectIndexText = specificSubjectIndexText.replace(/<think>[\\s\\S]*?<\\/think>\\n*/gi, '').trim();

                    // Filter by target entity type so each LLM only sees its own entities
                    if (pData.key) {
                        const targetTypeKey = pData.key;
                        let allowedKeywords = [];
                        if (targetTypeKey === 'characters') allowedKeywords = ['character', '角色', '人物'];
                        else if (targetTypeKey === 'props') allowedKeywords = ['prop', '道具', '物件'];
                        else if (targetTypeKey === 'environments') allowedKeywords = ['environment', 'env', '场景', '环境'];
                        else if (targetTypeKey === 'posters') allowedKeywords = ['poster', 'cover_poster', 'cover', '海报', '封面'];

                        const allEntityKeywords = ['character', '角色', '人物', 'prop', '道具', '物件', 'environment', 'env', '场景', '环境', 'poster', 'cover_poster', 'cover', '海报', '封面'];

                        const lines = specificSubjectIndexText.split('\\n');
                        const filteredLines = [];

                        for (let line of lines) {
                            const lineTrim = line.trim();
                            const isRowItem = /^(?:\\||[+\\\\-*]\\s*?\\[[a-zA-Z0-9_-]+\\]|[A-Za-z0-9_-]+\\s*\\|)/.test(lineTrim);
                            if (isRowItem) {
                                const lowerLine = line.toLowerCase();
                                const isEntityRow = allEntityKeywords.some(kw => lowerLine.includes(kw));
                                
                                if (isEntityRow) {
                                    const matchesTarget = allowedKeywords.some(kw => lowerLine.includes(kw));
                                    if (matchesTarget) {
                                        filteredLines.push(line);
                                    }
                                } else {
                                    // Likely a header row, keep it
                                    filteredLines.push(line);
                                }
                            } else {
                                // Normal text, project context, table separators, etc. keep it.
                                filteredLines.push(line);
                            }
                        }
                        specificSubjectIndexText = filteredLines.join('\\n').trim();
                    }

                    const subResult = await awaitAnalyzeSceneWithRecovery(
                        () => analyzeScene(
                            specificSubjectIndexText,  
                            pData.content, 
                            null, 
                            isPrimary ? (activeEpisode?.id || null) : null, // Only bind episode ID on the first one to avoid DB overwrite race conditions
                            analysisAttentionNotes, 
                            selectedReuseSubjectAssets, 
                            {
                                onTaskCreated: (taskId) => {
                                    if (isPrimary) {
                                        setActiveAnalysisTaskId(String(taskId || '').trim());
                                        saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt: phase2StartedAt, phase: 4 });
                                    }
                                }
                            }, 
                            projectId,
                            "script_analysis",
                            phase1SystemApiId,
                            `2_pass_generate_assets_${pData.key}`
                        ),
                        { startedAt: phase2StartedAt, baselineText: '', resultField: 'none' } // prevent persistence internally by passing no conflict
                    );

                    assetsGenCompletedCount++;
                    setAnalysisFlowStatus({
                        phase: "assets_gen",
                        message: t(`✨ 第四阶段资产生成中 (${assetsGenCompletedCount}/${targetAssetsCount} 个并发任务已完成)...`, `Running Stage 4 asset design (${assetsGenCompletedCount}/${targetAssetsCount} completed)...`),
                    });
                    
                    return { key: pData.key, result: subResult };
                })
            );"""
                        
text = re.sub(pattern, new_block, text, flags=re.DOTALL)

with open("frontend/src/pages/editor/components/ScriptEditor.jsx", "w", encoding="utf-8") as f:
    f.write(text)
