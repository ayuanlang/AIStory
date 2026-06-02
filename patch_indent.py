import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

match = re.search(r'        # Fire the generation task.*?return await self\._submit_and_poll_video[^\)]*\)', text, re.DOTALL)
if match:
    block = match.group(0)
    lines = block.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('            '):
            new_lines.append('        ' + line[12:])
        elif line.startswith('        '):
            new_lines.append('        ' + line[8:])
        else:
            new_lines.append(line)
            
    # wait wait, '# Fire the generation task' is indented with 8 spaces. The lines after it are 12 spaces.
    # We want everything to be 8 spaces relative to the function.
    # Let's write a targeted replace
    
    new_block = "\n".join(new_lines)
    text = text.replace(block, new_block)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Fixed indentation!")
else:
    print("Not found")