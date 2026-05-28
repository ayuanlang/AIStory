import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""                const stage2_2Text = extractAnalysisTextFromResult(stage2_2Result) || '';
                
                // Directly persist the clean Subject Index (Stage 2.1) without coupling it to Stage 2.2 Scenes.
                try {
                    if (onLog) onLog('Persisting clean Stage 2.1 Subject Index immediately...', 'process');
                    await persistLlmResultContent(String(stage2_1Text || '').trim(), 'ai_scene_analysis_subject_index', {
                        source: 'advanced-analysis-stage2_1-subject-index'
                    });
                } catch (persistErr) {
                    if (onLog) onLog(`Failed to persist clean Subject Index: ${persistErr?.message || persistErr}`, 'warning');
                }"""

new_block = r"""                const stage2_2Text = extractAnalysisTextFromResult(stage2_2Result) || '';
                
                // Extract clean Subject Index from Stage 2.1 Text before persisting
                const pureSections21 = extractAnalysisSections(stage2_1Text);
                const cleanSubjectIndexToPersist = pureSections21.hasStructuredSubjectIndex ? pureSections21.subjectIndexText : String(stage2_1Text || '').trim();

                // Directly persist the clean Subject Index (Stage 2.1) without coupling it to Stage 2.2 Scenes.
                try {
                    if (onLog) onLog('Persisting clean Stage 2.1 Subject Index immediately...', 'process');
                    await persistLlmResultContent(cleanSubjectIndexToPersist, 'ai_scene_analysis_subject_index', {
                        source: 'advanced-analysis-stage2_1-subject-index'
                    });
                } catch (persistErr) {
                    if (onLog) onLog(`Failed to persist clean Subject Index: ${persistErr?.message || persistErr}`, 'warning');
                }"""

if old_block in text:
    text = text.replace(old_block, new_block)
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Done refactoring Stage 2.1 Subject Index extraction!")
else:
    print("Old block not found!")
