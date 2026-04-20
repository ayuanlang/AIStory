import os

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "# Fallback to pure bracket Regex for ones that might not be in lookup" in line:
        skip = True
    if skip and "if not pairs:" in line:
        skip = False
        new_lines.append(line)
        continue
    if not skip:
        new_lines.append(line)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Cleaned!')