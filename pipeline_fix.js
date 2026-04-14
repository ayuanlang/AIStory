
const fs = require("fs");
const filepath = "C:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx";
let content = fs.readFileSync(filepath, "utf8");

const oldRegex = /const runPostImportSceneSubjectPipeline = useCallback\(async \(importReport, options = \{\}\) => \{[\s\S]*?\}, \[onLog, projectId, t\]\);/;

const newCode = `const runPostImportSceneSubjectPipeline = useCallback(async (importReport, options = {}) => {
        const importedSceneRows = Array.isArray(importReport?.importedSceneRows) ? importReport.importedSceneRows : [];
        const emptyReport = {
            checkedSceneCount: importedSceneRows.length,
            missingSceneCount: 0,
            missingItemCount: 0,
            missingSceneReports: [],
            supplementReport: {
                createdItems: [],
                skippedItems: [],
                failedItems: [],
                sceneReports: [],
                countsByType: { character: 0, prop: 0, environment: 0 },
            },
        };

        if (!projectId || importedSceneRows.length === 0) {
            return emptyReport;
        }

        const authoritativeSubjectText = llmRawResultContent || llmResultContent || activeEpisode?.ai_scene_analysis_result || "";
        
        let subjectIndexText = "";
        const match = authoritativeSubjectText.match(/###\\s*Subject Index[\\s\\S]*/i);
        if (match) {
            subjectIndexText = match[0];
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
            const promptRes = await fetchPrompt("subject_generation.txt").catch(() => null);
            const promptContent = promptRes?.content || "";

            const result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    subjectIndexText,
                    promptContent,
                    null,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    null,
                    projectId
                ),
                { startedAt: Date.now(), baselineText: "" }
            );

            const analyzedText = extractAnalysisTextFromResult(result);
            setLlmAssetRawResultContent(analyzedText);

            if (analyzedText) {
                // Automatically import the generated subjects
                await doImportText(analyzedText, "auto");
            }

            return emptyReport;
        } catch (error) {
            onLog?.(\`Asset generation failed: \${error.message}\`, "error");
            return emptyReport;
        }
    }, [llmRawResultContent, llmResultContent, activeEpisode, analysisAttentionNotes, selectedReuseSubjectAssets, projectId, awaitAnalyzeSceneWithRecovery, doImportText, onLog, t, setLlmAssetRawResultContent]);`;

if (oldRegex.test(content)) {
    content = content.replace(oldRegex, newCode);
    fs.writeFileSync(filepath, content);
    console.log("Replaced pipeline properly.");
} else {
    console.log("Could not find pipeline to replace");
}

