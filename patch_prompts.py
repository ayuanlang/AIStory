import codecs

with codecs.open('frontend/src/pages/editor/components/ScriptEditor.jsx', 'r', 'utf-8') as f:
    text = f.read()

target1 = '"scene_analysis.txt"'
repl1 = '"skills/scene_analysis_feature_stack/scene_planning.md"'

if target1 in text:
    text = text.replace(target1, repl1)
    print("Found and replaced scene_analysis.txt")

with codecs.open('frontend/src/pages/editor/components/ScriptEditor.jsx', 'w', 'utf-8') as f:
    f.write(text)
