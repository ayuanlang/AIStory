import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """                elif effective_provider == "doubao":
                    runtime_result = await self._handle_doubao_generation("""

if target in text:
    print("Found doubao logic.")
else:
    print("Could not find doubao logic.")
    
# Let's try finding grsai
target_grsai = """                if effective_provider == "grsai":"""
if target_grsai in text:
    print("Found grsai logic.")
else:
    print("Could not find grsai logic.")

# Match 'doubao' near '_handle_doubao_generation('
matches = re.finditer(r'elif effective_provider == "doubao":[\s\S]{0,300}?(?=\elif|\_|return)', text)
for m in matches:
    print("Match Doubao:", m.group(0))
