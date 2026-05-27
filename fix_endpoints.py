import re

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Replace the broken string 
text = text.replace('if "供应商调用失? in detail:', 'if "供应商调用失败" in detail:')
text = text.replace('return f"{vendor}供应商调用失? {detail}"', 'return f"{vendor}供应商调用失败: {detail}"')

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
