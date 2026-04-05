with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'elif "text-to-video"' in l:
        for j in range(i, i+15):
            print(f'{j+1:04d}: {lines[j]}', end='')
