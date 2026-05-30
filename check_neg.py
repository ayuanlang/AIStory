with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'negative' in line.lower() and ('+' in line or 'f"' in line or "f'" in line or 'format' in line):
        print(f'media_service {i+1}: {line.strip()}')

with open('backend/app/services/zlhub_gen.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'negative' in line.lower() and ('+' in line or 'f"' in line or "f'" in line or 'format' in line):
        print(f'zlhub {i+1}: {line.strip()}')

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'negative' in line.lower() and ('+' in line or 'f"' in line or "f'" in line or 'format' in line):
        print(f'endpoints {i+1}: {line.strip()}')
