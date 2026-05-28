import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""            let finalSubjectIndexText = subjectIndexText;
            const designProjectContextSection = buildStage1ProjectContextSection()"""

new_block = r"""            let finalSubjectIndexText = subjectIndexText;
            // Hotfix: Ensure any trailing Scenes markdown that accidentally leaked into the Subject Index gets cleanly removed
            const scenesOftMatch = finalSubjectIndexText.match(/(?:^|\n)\s*(?:###?\s*(?:-1\)\s*类型研判|Scenes|场景列表))/i);
            if (scenesOftMatch && scenesOftMatch.index >= 0) {
                finalSubjectIndexText = finalSubjectIndexText.slice(0, scenesOftMatch.index).trim();
            }
            
            const designProjectContextSection = buildStage1ProjectContextSection()"""

if old_block in text:
    text = text.replace(old_block, new_block)
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched hotfix into ScriptEditor")
else:
    print("Old block not found for hotfix")

