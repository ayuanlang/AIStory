import re
with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', encoding='utf-8') as f:
    text = f.read()

statuses = set(re.findall(r'status="([^"]+)"', text))
print("STATUSES:", statuses)