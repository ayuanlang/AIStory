import sys
sys.path.append('c:/AS/AIStory/backend')
import json
import re

f = open('c:/AS/AIStory/debug_append.txt', 'r', encoding='utf-8')
d = json.loads(f.read().split('================\n')[-4])
prompt = d['prompt']
char_name = 'Mu Yiruo'
text = str(prompt).strip()
prefix = '@Image2 '
escaped_entity = re.escape(char_name)

anchor_patterns = [
    rf'(?:CHAR|ENV|PROP)\s*:\s*[\[¡¾]\s*@?{escaped_entity}\s*[\]¡¿](?:\([^\)]*\))?',
    rf'[\[¡¾]\s*@?{escaped_entity}\s*[\]¡¿](?:\([^\)]*\))?'
]

def _prepend_prefix(match: re.Match[str]) -> str:
    token = str(match.group(0) or '')
    if token.startswith(prefix):
        return token
    return f'{prefix}{token}'

text, subs = re.subn(anchor_patterns[0], _prepend_prefix, text, flags=re.IGNORECASE)
print('subs (pattern0):', subs)
print('@Image2 count:', text.count('@Image2'))
