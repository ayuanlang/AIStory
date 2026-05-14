with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('updated_text = f"ÑÓ³¤')
print('Index:', idx)
print(text[idx-500:idx+800])
