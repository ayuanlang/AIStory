with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('def _handle_kie_generation')
print(text[idx:idx+1500])
