import re

filepath = 'C:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'(let subjectIndexText = \"\";.*?const promptContent = promptRes\?\.content \|\| \"\";\s+const result = await awaitAnalyzeSceneWithRecovery\()'

repl = r'''let subjectIndexText = "";

        onLog?.([Asset Gen Tracking] Initial authoritativeText length: \, "info");

        const match = authoritativeSubjectText.match(/(?:###?|##)\s*(?:Subject Index|角色|道具|场景|设计资产|Entities)[\s\S]*/i);
        if (match) {
            subjectIndexText = match[0];
            onLog?.([Asset Gen Tracking] Extracted Subject Index (length: \), "success");
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

            const result = await awaitAnalyzeSceneWithRecovery('''

text = re.sub(pattern, lambda m: repl, text, flags=re.S)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print('Success Python Replace')
