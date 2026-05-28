import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""const endMarkers = [
                /^\s*-{4,}\s*$/im,
                /^\s*(?:###?\s*)?(?:Project\s*Visual\s*Backfill|第三部分|Final\s*Consistency\s*Report|一致性检查)\b/im,
                /^\s*\{\s*"project_visual_backfill"\s*:/im,
            ];"""
            
new_block = r"""const endMarkers = [
                /^\s*-{4,}\s*$/im,
                /^\s*(?:###?\s*)?(?:Project\s*Visual\s*Backfill|第三部分|Final\s*Consistency\s*Report|一致性检查)\b/im,
                /^\s*\{\s*"project_visual_backfill"\s*:/im,
                /^\s*(?:(?:##|###)\s*(?:-1\)|Scenes?|场景列表))|(?:\*\*\s*(?:Scenes?)\s*\*\*)|(?:-{3,}\n\s*(?:Scenes?))/im,
                /^\s*(?:###?\s*(?:-1\)\s*类型研判|Scenes|场景列表))/im,
            ];"""
            
if old_block in text:
    text = text.replace(old_block, new_block)
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched endMarkers")
else:
    print("Not found endMarkers")

