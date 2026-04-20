with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
text = re.sub(r'    \\"\\"\\"[\r\n]+    safe_kind', '    """\n    safe_kind', text)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
