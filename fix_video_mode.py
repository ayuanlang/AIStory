import re
import os

filepath = 'frontend/src/pages/editor/editorHelpers.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# Patched to support entity_refs_start_end
text = text.replace(
    "if (rawMode === 'refs_video' || rawMode === 'entity_refs') return 'entity_refs';",
    "if (rawMode === 'refs_video' || rawMode === 'entity_refs') return 'entity_refs';\n    if (rawMode === 'entity_refs_start_end') return 'entity_refs_start_end';"
)

old_build = '''    if (mode === 'entity_refs') {
        return normalizeMediaRefList(entityRefUrls);
    }

    if (mode === 'end') {'''

new_build = '''    if (mode === 'entity_refs') {
        return normalizeMediaRefList(entityRefUrls);
    }

    if (mode === 'entity_refs_start_end') {
        const combined = [...(entityRefUrls || [])];
        if (startRef && !combined.includes(startRef)) combined.push(startRef);
        if (endRef && !combined.includes(endRef)) combined.push(endRef);
        return normalizeMediaRefList(combined);
    }

    if (mode === 'end') {'''

text = text.replace(old_build, new_build)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated editorHelpers.jsx')
