import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = 'self._do_volc_request("POST", "CreateAssetGroup", "2024-01-01", "{}", "ark", ak, sk)'
import json
replacement = 'self._do_volc_request("POST", "CreateAssetGroup", "2024-01-01", json.dumps({"Name": "seedance_asset"}), "ark", ak, sk)'

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched CreateAssetGroup!")
else:
    print("Not found")
