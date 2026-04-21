const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'frontend/src/pages/editor/components/ScriptEditor.jsx');
let content = fs.readFileSync(filePath, 'utf8');

// 1. Update saveAnalysisTaskMarker to support phase
content = content.replace(
    /saveAnalysisTaskMarker\(\s*(.*?),\s*\{\s*taskId,\s*startedAt\s*\}\s*\)/g,
    'saveAnalysisTaskMarker($1, { taskId, startedAt, phase: 1 })'
);

// wait, first check if `phase` is already passed.
// let's do more explicit replace.
const phase2CallOld = `const result = await analyzeScene(
                finalSubjectIndexText,
                finalPromptContent,
                null,
                activeEpisode?.id || null,
                analysisAttentionNotes,
                selectedReuseSubjectAssets,
                null, // No runtime hooks (we just want it to wait via the default \`asyncLLMPost\` behavior)
                projectId,
                "subject_generation", // explicitly setting functionName
                null,                 // default systemApiId
                "2_pass_generate_assets" // overriding sceneAnalysisMode internally just to bust the dedupe cache for the second call
            );`;

const phase2CallNew = `const result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    finalSubjectIndexText,
                    finalPromptContent,
                    null,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            setActiveAnalysisTaskId(String(taskId || '').trim());
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt: Date.now(), phase: 2 });
                        }
                    },
                    projectId,
                    "subject_generation",
                    null,
                    "2_pass_generate_assets"
                ),
                { startedAt: Date.now(), baselineText: '' }
            );`;

content = content.replace(phase2CallOld, phase2CallNew);

fs.writeFileSync(filePath, content);
console.log("Phase 2 analyzeScene call updated.");
