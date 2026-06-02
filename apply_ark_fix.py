import os
file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace “Type” with “AssetType” and “image” with “Image”
text = text.replace('"Type": "image",', '"AssetType": "Image",')

old_code = """        if str(ref_image).startswith("http"):
            import requests
            img_b64 = base64.b64encode(requests.get(ref_image).content).decode("utf-8")
        else:
            marker = ";base64,"
            idx = ref_image.find(marker)
            if idx != -1:
                img_b64 = ref_image[idx + len(marker):].strip()
            else:
                img_b64 = ref_image
                
        try:"""

new_code = """        if str(ref_image).startswith("http"):
            import requests
            img_b64 = base64.b64encode(requests.get(ref_image).content).decode("utf-8")
            asset_url = ref_image
        else:
            marker = ";base64,"
            idx = ref_image.find(marker)
            if idx != -1:
                img_b64 = ref_image[idx + len(marker):].strip()
            else:
                img_b64 = ref_image
            asset_url = ref_image if str(ref_image).startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
                
        try:"""

text = text.replace(old_code, new_code)
text = text.replace('"URL": ref_image,', '"URL": asset_url,')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
