with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'status="succeeded"' in line:
            print(f"{i+1}: {line.strip()}")