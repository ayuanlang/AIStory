import urllib.request
import re

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# fixing the known one: line 7123: `if "增加想象? in raw or ...` -> `if "增加想象力" in raw or ...`
text = text.replace('if "增加想象\ufffd? in raw', 'if "增加想象力" in raw')

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
