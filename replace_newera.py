import re
with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

pat = r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'年代\', \'Era\'\)\}</label>\s*<select.*?value=\{newEra\}.*?onChange=\{.*?setNewEra.*?\}>.*?</select>'
repl = r'<InputGroup label={t("年代", "Era")} value={newEra} onChange={setNewEra} list={projectCreateOptions.era} />'

match = re.search(pat, text, flags=re.DOTALL)
if match:
    text = text[:match.start()] + repl + text[match.end():]
else:
    print("Not found newEra")

with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
