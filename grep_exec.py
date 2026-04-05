import re
p = 'c:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
c = open(p, 'r', encoding='utf-8').read()
match = re.search(r'(const executeAnalysis = async.*?)(?=\n\s+const)', c, flags=re.DOTALL|re.MULTILINE)
if match:
    open('exec_analysis.txt', 'w', encoding='utf-8').write(match.group(1))
    print("Saved")
else:
    print("Not found")
