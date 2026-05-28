import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""                const stage2_2Text = extractAnalysisTextFromResult(stage2_2Result) || '';
                
                stage2PhaseRawText = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\n\n');
                finalAnalysisText = [String(analyzedText || '').trim(), stage2PhaseRawText].filter(Boolean).join('\n\n');

                importSourceText = finalAnalysisText;
                phaseMarks.persistStartedAt = Date.now();
                try {
                    if (onLog) onLog('Persisting split-flow combined raw LLM output immediately after Stage 2 return...', 'process');
                    await persistLlmResultContent(finalAnalysisText || '', 'ai_scene_analysis_result', {
                        source: 'advanced-analysis-split-combined-immediate',
                        stage1RawText: stage1PhaseRawText,
                        stage2RawText: stage2PhaseRawText,
                    });
                    finalRawResultPersistedEarly = true;
                } catch (persistErr) {
                    if (onLog) onLog(`Immediate split-flow raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                } finally {
                    phaseMarks.persistFinishedAt = Date.now();
                }
                analysisSections = extractAnalysisSections(finalAnalysisText);"""

new_block = r"""                const stage2_2Text = extractAnalysisTextFromResult(stage2_2Result) || '';
                
                // Directly persist the clean Subject Index (Stage 2.1) without coupling it to Stage 2.2 Scenes.
                try {
                    if (onLog) onLog('Persisting clean Stage 2.1 Subject Index immediately...', 'process');
                    await persistLlmResultContent(String(stage2_1Text || '').trim(), 'ai_scene_analysis_subject_index', {
                        source: 'advanced-analysis-stage2_1-subject-index'
                    });
                } catch (persistErr) {
                    if (onLog) onLog(`Failed to persist clean Subject Index: ${persistErr?.message || persistErr}`, 'warning');
                }
                
                stage2PhaseRawText = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\n\n');
                finalAnalysisText = [String(analyzedText || '').trim(), stage2PhaseRawText].filter(Boolean).join('\n\n');

                importSourceText = finalAnalysisText;
                phaseMarks.persistStartedAt = Date.now();
                try {
                    if (onLog) onLog('Persisting split-flow combined raw LLM output immediately after Stage 2 return...', 'process');
                    await persistLlmResultContent(finalAnalysisText || '', 'ai_scene_analysis_result', {
                        source: 'advanced-analysis-split-combined-immediate',
                        stage1RawText: stage1PhaseRawText,
                        stage2RawText: stage2PhaseRawText,
                    });
                    finalRawResultPersistedEarly = true;
                } catch (persistErr) {
                    if (onLog) onLog(`Immediate split-flow raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                } finally {
                    phaseMarks.persistFinishedAt = Date.now();
                }
                // Override the extraction to ensure the pure stage2_1Text acts as the authoritative source
                analysisSections = extractAnalysisSections(stage2PhaseRawText);
                if (!analysisSections.hasStructuredSubjectIndex) {
                    // Try parsing pure 2.1 text just in case the extract logic trips over 2.2
                    const pureSections = extractAnalysisSections(stage2_1Text);
                    if (pureSections.hasStructuredSubjectIndex) {
                        analysisSections.hasStructuredSubjectIndex = true;
                        analysisSections.subjectIndexText = pureSections.subjectIndexText;
                    }
                }"""

if old_block in text:
    text = text.replace(old_block, new_block)
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Done refactoring Stage 2 persistence!")
else:
    print("Old block not found!")
