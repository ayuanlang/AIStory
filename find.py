with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.finditer(r'onChange=\{\(e\) => setUsePrevVideo\(e\.target\.checked\)\}', text)
for m in matches:
    idx = m.start()
    print('Match:')
    print(text[max(0, idx-100):min(len(text), idx+100)])
