import re

path = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Remove the state
text = re.sub(r'\s*const \[isGeneratingScript, setIsGeneratingScript\] = useState\(false\);\n', '\n', text)

# Remove the button
btn_pattern = re.compile(
    r'\s*<button \s*onClick=\{async \(\) => \{[\s\S]*?\{t\(\'AI一键生成本集\', \'AI Gen Episode\'\)\}\s*</button>',
    re.MULTILINE
)
text = btn_pattern.sub('', text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Done modification script.")
