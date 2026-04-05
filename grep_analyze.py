import re
p = 'c:/AIStory/backend/app/api/endpoints.py'
c = open(p, 'r', encoding='utf-8').read()
match = re.search(r'async def analyze_scene\(.*?(?=^@router|^async def|^def)', c, flags=re.DOTALL|re.MULTILINE)
if match:
    open('endpoints_analyze.txt', 'w', encoding='utf-8').write(match.group(0))
else:
    print("Not found")
