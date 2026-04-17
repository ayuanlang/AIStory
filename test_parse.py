with open('backend/app/api/endpoints.py', encoding='utf-8') as f:  
  lines = f.readlines()  
for i, l in enumerate(lines):  
  if 'def analyze_scene' in l:  
    for j in range(i, i+600):  
      if 'prompt' in lines[j] or 'content' in lines[j]:  
        print(f'{j+1}: {lines[j].strip()}')  
