import re
import sys

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

replacement = """                                  assetRawText: activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                                  stage2_1Text: globalStage2_1Text || undefined,
                                  stage1RawText: stage1PhaseRawText,
                                  stage2RawText: stage2PhaseRawText,"""

text = text.replace("                                  assetRawText: activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',", replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated ai_stage_outputs config!")
