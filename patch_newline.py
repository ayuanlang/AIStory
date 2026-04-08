lines = open('backend/app/services/media_service.py', 'r', encoding='utf-8').readlines()
new_lines = []
for line in lines:
    if r'\n                payload["lastFrameUrl"]' in line:
        line = line.replace(r'\n                payload["lastFrameUrl"]', '\n                payload["lastFrameUrl"]')
    new_lines.append(line)
with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Fixed newline literal issue!')
