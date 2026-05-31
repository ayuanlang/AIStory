import re
import sys

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add definitions
ref_insert = """    const lastLoadedAnalysisRef = useRef(null);
    const latestAssetRawTextRef = useRef('');
    const latestAnalysisRawTextRef = useRef('');
    const latestStage2_1TextRef = useRef('');
"""
text = text.replace("    const lastLoadedAnalysisRef = useRef(null);", ref_insert)

# 2. Update persistLlmResultContent
persist_replacement = """        try {
            const nextContent = String(content || '');
            const updatePayload = { [resultField]: nextContent };
            const logSource = String(options?.source || 'unspecified').trim() || 'unspecified';

            if (resultField === 'ai_scene_analysis_result') {
                latestAnalysisRawTextRef.current = nextContent;
                if (options?.stage2_1Text !== undefined) {
                    latestStage2_1TextRef.current = options.stage2_1Text;
                }
                const extractedSections = extractAnalysisSections(nextContent);
                let subjectIndexValue = extractedSections?.hasStructuredSubjectIndex
                    ? String(extractedSections.subjectIndexText || '').trim()
                    : '';
                if (options?.stage2_1Text !== undefined) {
                    subjectIndexValue = String(options.stage2_1Text || '').trim();
                }
                const looksLikeAdaptedScript = /(?:###?\\s*第二部分[:：]?\\s*修改后的剧本|###?\\s*Second\\s*Part[:：]?\\s*Adapted\\s*Script|【场景\\s*|Scene\\s*\\d+)/i.test(nextContent);
                const adaptationValue = looksLikeAdaptedScript
                    ? String(extractStage1AdaptedScriptBody(nextContent) || '').trim()
                    : '';

                updatePayload.ai_scene_analysis_subject_index = subjectIndexValue;
                updatePayload.ai_scene_analysis_adaptation = adaptationValue;
                updatePayload.ai_stage_outputs = JSON.stringify(buildStageOutputsObject({
                    analysisRawText: nextContent,
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: options?.stage1RawText || '',
                    stage2RawText: options?.stage2RawText || '',
                    stage2_1Text: options?.stage2_1Text !== undefined ? options.stage2_1Text : (latestStage2_1TextRef.current || subjectIndexValue),
                }), null, 2);

                onLog?.(`[Analysis Writeback] field=${resultField} source=${logSource} raw_len=${nextContent.length} subject_index_len=${subjectIndexValue.length} adaptation_len=${adaptationValue.length}`, 'info');
            } else if (resultField === 'ai_entity_design_result') {
                latestAssetRawTextRef.current = nextContent;
                updatePayload.ai_stage_outputs = JSON.stringify(buildStageOutputsObject({
                    analysisRawText: latestAnalysisRawTextRef.current || activeEpisode?.ai_scene_analysis_result || llmRawResultContent || '',
                    assetRawText: nextContent,
                    stage2_1Text: latestStage2_1TextRef.current || undefined
                }), null, 2);

                onLog?.(`[Analysis Writeback] field=ai_stage_outputs source=${logSource} bundle_len=${String(updatePayload.ai_stage_outputs || '').length}`, 'info');
            } else if (resultField === 'ai_scene_analysis_subject_index') {
                latestStage2_1TextRef.current = nextContent;
                updatePayload[resultField] = nextContent;
            } else {
                onLog?.(`[Analysis Writeback] field=${resultField} source=${logSource} raw_len=${nextContent.length}`, 'info');
            }

            await onUpdateEpisodeInfo(activeEpisode.id, updatePayload);
        } catch (e) {"""

# Find the try block inside persistLlmResultContent to replace
start_str = "        try {\n            const nextContent = String(content || '');"
end_str = "            await onUpdateEpisodeInfo(activeEpisode.id, updatePayload);\n        } catch (e) {"

start_idx = text.find(start_str)
end_idx = text.find(end_str)

if start_idx != -1 and end_idx != -1:
    text = text[:start_idx] + persist_replacement + text[end_idx + len(end_str):]
else:
    print("Could not find persistLlmResultContent body!")
    sys.exit(1)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied useRef tracking to avoid closure staleness!")
