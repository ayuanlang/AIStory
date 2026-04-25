const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'frontend/src/pages/editor/components/ScriptEditor.jsx');
let content = fs.readFileSync(filePath, 'utf8');

// Look for the analyzeScene block around line 1700-1800 where `2_pass_generate_assets` is used.
content = content.replace(
    /const result = await analyzeScene\(\s*finalSubjectIndexText,\s*finalPromptContent,\s*null,\s*activeEpisode(?:\?)?\.id(?: \|\| null)?,\s*analysisAttentionNotes,\s*selectedReuseSubjectAssets,\s*null,\s*projectId,\s*"(?:script_analysis|subject_generation)",\s*null,\s*"2_pass_generate_assets"\s*\);/m,
    `const result = await awaitAnalyzeSceneWithRecovery(
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
            );`
);

fs.writeFileSync(filePath, content);
console.log('Fixed Phase 2 analyzeScene Call');
