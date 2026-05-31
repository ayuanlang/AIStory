import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# We want to replace the block starting from:
# if (onLog) onLog('Stage 2.1 completed. Now starting Stage 2.2 (Beats Generation)...', 'info');
# up to the end of executeAdvancedAnalysis

def search_text():
    match = re.search(r"if \(onLog\) onLog\('Stage 2\.1 completed\. Now starting Stage 2\.2 \(Beats Generation\)\.\.\.', 'info'\);(.*?)setAnalysisUiReport\(\{\s*status: 'completed',", text, re.DOTALL)
    if match:
        return match.group(1)
    else:
        return "NOT FOUND"

block = search_text()
with open('c:\\AS\\AIStory\\extracted_block.txt', 'w', encoding='utf-8') as f:
    f.write(block)
