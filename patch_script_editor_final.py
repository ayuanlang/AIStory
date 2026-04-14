import re

file_path = 'C:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace UI Map
ui_block_old = r"\[\s*\{\s*key:\s*'autosaving'.*?\},\s*\{\s*key:\s*'analyzing'.*?\},\s*\{\s*key:\s*'importing'.*?\},\s*\{\s*key:\s*'checking_scene_subjects'.*?\},\s*\{\s*key:\s*'supplementing_scene_subjects'.*?\},\s*\{\s*key:\s*'completed'.*?\},\s*\]"
ui_block_new = """[
                            { key: 'autosaving', label: '自动保存' },
                            { key: 'analyzing_scene', label: '场景分析' },
                            { key: 'saving_scenes', label: '场景保存' },
                            { key: 'generating_assets', label: '资产生成' },
                            { key: 'importing_assets', label: '导入资产' },
                            { key: 'completed', label: '分析报告' },
                        ]"""

content, count = re.subn(ui_block_old, ui_block_new, content, count=1, flags=re.DOTALL)
print(f"Replaced UI block: {count}")

# 2. Update stepOrder
step_order_old = "const stepOrder = ['autosaving', 'analyzing', 'importing', 'checking_scene_subjects', 'supplementing_scene_subjects', 'completed'];"
step_order_new = "const stepOrder = ['autosaving', 'analyzing_scene', 'saving_scenes', 'generating_assets', 'importing_assets', 'completed'];"
content = content.replace(step_order_old, step_order_new)
print("Replaced stepOrder")

# 3. Update isFailed
is_failed_old = "const isFailed = isTerminalFailed && step.key === 'analyzing';"
is_failed_new = "const isFailed = isTerminalFailed && step.key === 'analyzing_scene';"
content = content.replace(is_failed_old, is_failed_new)
print("Replaced isFailed")

# 4. Update the condition `stepIndex <= 3`
content = content.replace("? stepIndex <= 3", "? stepIndex <= 5")
print("Replaced stepIndex <= 3 with 5")


# 5. Fix markdown logic
lines = content.split('\n')
for i, l in enumerate(lines):
    if 'setLlmRawResultContent(analyzedText || "");' in l:
        indent = l[:len(l) - len(l.lstrip())]
        lines.insert(i, indent + 'const scenesText = analyzedText ? analyzedText.split(/\\n-+-+\\n?/)[0] : "";')
        break

# Since we inserted, we find setLlmResultContent again
for i, l in enumerate(lines):
    if 'setLlmResultContent(normalizeLlmMarkdownTable(analyzedText || ""));' in l:
        lines[i] = lines[i].replace('analyzedText || ""', 'scenesText')

    if 'importReport = await runAutoImportAndSwitchToScenes(analyzedText || "", { switchToScenes: false });' in l:
        lines[i] = lines[i].replace('analyzedText || ""', 'scenesText')

content = '\n'.join(lines)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done patching.")
