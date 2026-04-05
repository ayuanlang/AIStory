import re
p = 'c:/AIStory/backend/app/api/endpoints.py'
c = open(p, 'r', encoding='utf-8').read()
match = re.search(r'async def _await_analyze_scene_segment\(.*?(?=async def |def )', c, flags=re.DOTALL)
if match:
    print(match.group(0)[:1500])
else:
    print("Not found")
