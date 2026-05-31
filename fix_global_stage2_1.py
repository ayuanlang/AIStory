import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

replacement = """
            const stage2_1Text = extractAnalysisTextFromResult(stage2_1Result) || '';
            let globalStage2_1Text = stage2_1Text;
            if (onLog) onLog('Stage 2.1 completed. Kicking off Stage 2.2 (Beats) and Stage 3 (Asset Design) concurrently for restart...', 'info');
"""

text = text.replace("""
            const stage2_1Text = extractAnalysisTextFromResult(stage2_1Result) || '';
            globalStage2_1Text = stage2_1Text;
            if (onLog) onLog('Stage 2.1 completed. Kicking off Stage 2.2 (Beats) and Stage 3 (Asset Design) concurrently for restart...', 'info');
""", replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed globalStage2_1Text definition!")
