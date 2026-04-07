import re

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Pattern captures \1: TARGET_ID and \2: NEXT_DATA
pattern = r'setEditingShot\(\s*\(?prev\)?\s*=>\s*\(\s*\(?prev\s*&&\s*(?:String\()?prev(?:(?:\?)?\.id)?\)?\s*===\s*([A-Za-z0-9_.]+(?:\.id)?)\)?\s*\?\s*\{\s*\.\.\.prev,\s*\.\.\.([A-Za-z0-9_.]+)\s*\}\s*:\s*prev\s*\)\s*\);?'

replacement = r'''setShots(prevShots => prevShots.map(s => (String(s?.id || '') === String(\1) ? { ...s, ...\2 } : s)));
                                        setEditingShot(prev => (prev && String(prev.id) === String(\1) ? { ...prev, ...\2 } : prev));'''

text = re.sub(pattern, replacement, text)

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patch applied for setShots sync!")
