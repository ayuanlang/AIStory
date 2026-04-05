import re
p = 'c:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
c = open(p, 'r', encoding='utf-8').read()

target = '''            {(analysisFlowStatus.phase !== 'idle' || analysisUiReport) && (analysisUiReport || (isAnalyzing && llmRawResultContent)) && ('''
replacement = '''            {(analysisFlowStatus.phase !== 'idle' || analysisUiReport) && analysisUiReport && ('''

c = c.replace(target, replacement)
open(p, 'w', encoding='utf-8').write(c)
print("Done")
