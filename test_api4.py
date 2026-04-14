import sys; sys.path.append('frontend/src/services')
with open('frontend/src/services/api.js', 'r', encoding='utf-8') as f:
 lines = f.readlines()
for i, line in enumerate(lines):
 if 'export const generateImage = async' in line:
  print(''.join(lines[i:i+30]))
