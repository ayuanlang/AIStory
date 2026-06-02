import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """            asset_payload = json.dumps({
                "AssetGroupId": asset_group_id,
                "Type": "image",
                "Data": img_b64
            })"""

replacement = """            asset_payload = json.dumps({
                "AssetGroupId": asset_group_id,
                "Type": "image",
                "Data": img_b64,
                "Name": "seedance_image"
            })"""

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched CreateAsset!")
else:
    print("Not found")