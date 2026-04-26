with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('async def _maybe_moderate_zlhub_image(selfasync def _maybe_moderate_zlhub_image(self', 'async def _maybe_moderate_zlhub_image(self', 1)

with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Fixed duplicate string')
