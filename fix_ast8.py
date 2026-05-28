import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""                const authoritativeSubjectText = explicitText || llmRawResultContent || llmResultContent || activeEpisode?.ai_scene_analysis_result || '';
                const persistedSubjectIndexText = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
                const extractedSections = extractAnalysisSections(authoritativeSubjectText);
                let subjectIndexText = persistedSubjectIndexText || (extractedSections.hasStructuredSubjectIndex ? (extractedSections.subjectIndexText || "") : "");
                let adaptationBodyText = String(activeEpisode?.ai_scene_analysis_adaptation || '').trim();"""

new_block = r"""                const authoritativeSubjectText = explicitText || llmRawResultContent || llmResultContent || activeEpisode?.ai_scene_analysis_result || '';
                const persistedSubjectIndexText = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
                const extractedSections = extractAnalysisSections(authoritativeSubjectText);
                let subjectIndexText = options.explicitSubjectIndexText || persistedSubjectIndexText || (extractedSections.hasStructuredSubjectIndex ? (extractedSections.subjectIndexText || "") : "");
                let adaptationBodyText = String(activeEpisode?.ai_scene_analysis_adaptation || '').trim();"""

if old_block in text:
    text = text.replace(old_block, new_block)
    
    old_call_block = r"""            postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, finalAnalysisText);"""
    new_call_block = r"""            postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, finalAnalysisText, {
                explicitSubjectIndexText: analysisSections?.subjectIndexText || ''
            });"""
            
    if old_call_block in text:
        text = text.replace(old_call_block, new_call_block)
        
        # Also let's fix the `analysisSections` population to ensure we always use stage2_1Text as the pure source
        old_override_block = r"""                // Override the extraction to ensure the pure stage2_1Text acts as the authoritative source
                analysisSections = extractAnalysisSections(stage2PhaseRawText);
                if (!analysisSections.hasStructuredSubjectIndex) {
                    // Try parsing pure 2.1 text just in case the extract logic trips over 2.2
                    const pureSections = extractAnalysisSections(stage2_1Text);
                    if (pureSections.hasStructuredSubjectIndex) {
                        analysisSections.hasStructuredSubjectIndex = true;
                        analysisSections.subjectIndexText = pureSections.subjectIndexText;
                    }
                }"""
        
        new_override_block = r"""                // Override the extraction to ensure the pure stage2_1Text acts as the authoritative source
                analysisSections = extractAnalysisSections(stage2PhaseRawText);
                // We unconditionally treat stage2_1Text as our subject index
                analysisSections.hasStructuredSubjectIndex = true;
                analysisSections.subjectIndexText = String(stage2_1Text || '').trim();"""
                
        if old_override_block in text:
            text = text.replace(old_override_block, new_override_block)
            
            with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
                f.write(text)
            print("Done refactoring Stage 3 subject passing!")
        else:
            print("Override block not found")
    else:
        print("Call block not found")
else:
    print("Old block not found!")
