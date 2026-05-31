import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# We need to replace code from:
# if (onLog) onLog('Stage 2.1 completed. Now starting Stage 2.2 (Beats Generation)...', 'info');
# down to the end of executeAdvancedAnalysis, but we have to be careful with the else block (single flow).

# Let's inspect the target zone first
match = re.search(r"if \(onLog\) onLog\('Stage 2\.1 completed\. Now starting Stage 2\.2 \(Beats Generation\)\.\.\.', 'info'\);", text)
print("Found start:", match is not None)

match2 = re.search(r"if \(!analysisSections\.hasStructuredSubjectIndex\) \{", text)
print("Found end 1:", match2 is not None)
