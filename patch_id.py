import os

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = 'asset_group_id = group_res.get("AssetGroupId")'
replacement = 'asset_group_id = group_res.get("AssetGroupId") or group_res.get("Id")'

if target in text:
    new_text = text.replace(target, replacement)
    
    target2 = 'asset_id = asset_res.get("Asset", {}).get("AssetId")'
    replacement2 = 'asset_id = asset_res.get("Asset", {}).get("AssetId") or asset_res.get("Asset", {}).get("Id") or asset_res.get("Id")'
    
    new_text = new_text.replace(target2, replacement2)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched ID extraction!")
else:
    print("Not found")