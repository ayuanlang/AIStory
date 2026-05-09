import re

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Add tabs state and handleCreate changes (done in previous run if the script executed write... Oh wait, in previous script I set .write(text) out of the variables. So it only modified 	ext but left everything intact except handleCreate and subtab. Let's verify:
