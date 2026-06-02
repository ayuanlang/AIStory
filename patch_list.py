import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """        ref_image = reference_image_url
        if not ref_image:
            return {"error": "seedance 2.0 requires an image reference"}"""

replacement = """        ref_image = reference_image_url
        if isinstance(ref_image, list):
            ref_image = ref_image[0] if len(ref_image) > 0 else None
            
        if not ref_image:
            return {"error": "seedance 2.0 requires an image reference"}"""

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched successfully!")
else:
    print("Target not found!")
