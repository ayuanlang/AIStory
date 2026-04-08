lines = open('backend/app/services/media_service.py', 'r', encoding='utf-8').readlines()
new_lines = []
for i, line in enumerate(lines):
    if line.strip() == 'if resolved_last_frame and ("/openapi/v2/rhart-video/sparkvideo" in endpoint_lower):':
        new_lines.append('            if resolved_last_frame and ("/openapi/v2/rhart-video/sparkvideo" in endpoint_lower):\\n')
    else:
        new_lines.append(line)
with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Fixed!')
