import re
with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for i, line in enumerate(lines):
    if 'video_prompt = _append_video_api_ref_mapping' in line:
        for idx in range(i-20, i+5):
            print(lines[idx])
        break
