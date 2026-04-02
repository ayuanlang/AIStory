import re

with open('c:/AIStory/frontend/src/pages/editor/components/ProjectOverview.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# patch analyzeProjectNovel
text = text.replace(
    'analyzeProjectNovel(id, { novel_text: text })',
    "analyzeProjectNovel(id, { novel_text: text, function_name: 'script_analysis' })"
)

# what else is there? "generate_subjects"
# How does ProjectOverview use generate_subjects?
# Let's search inside text for generateProjectCharacterProfile or something similar.

with open('c:/AIStory/frontend/src/pages/editor/components/ProjectOverview.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

