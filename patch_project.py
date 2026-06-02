import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target1 = """            parts = api_key.split(":", 2)
            ak = parts[0]
            sk = parts[1]
            dp_token = parts[2]
        else:"""

replacement1 = """            parts = api_key.split(":", 2)
            ak = parts[0]
            sk = parts[1]
            dp_token = parts[2]
            
        project_name = config.get("config", {}).get("project_name", "default")
        if ":" in dp_token:
            subparts = dp_token.split(":", 1)
            dp_token = subparts[0]
            project_name = subparts[1]
            
        if not ak or not sk or not dp_token:"""

if target1 in text:
    new_text = text.replace(target1, replacement1)
    
    # Also patch CreateAssetGroup and CreateAsset
    new_text = new_text.replace('json.dumps({"Name": "seedance_asset"})', 'json.dumps({"Name": "seedance_asset", "ProjectName": project_name})')
    
    new_text = new_text.replace('"Name": "seedance_image"', '"Name": "seedance_image",\n                "ProjectName": project_name')
    
    new_text = new_text.replace('json.dumps({"Id": asset_id})', 'json.dumps({"Id": asset_id, "ProjectName": project_name})')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched ProjectName!")
else:
    print("Not found")