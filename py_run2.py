import os
file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

old_code = '''poll_res = self._do_volc_request("POST", "GetAsset", "2024-01-01", poll_req, "ark", ak, sk)
                status = poll_res.get("Asset", {}).get("Status", "processing")
                if status == "ready":'''

new_code = '''poll_res = self._do_volc_request("POST", "GetAsset", "2024-01-01", poll_req, "ark", ak, sk)
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"GetAsset response: {poll_res}")
                except:
                    print(f"GetAsset response: {poll_res}")
                    
                status = poll_res.get("Asset", {}).get("Status", "")
                if not status:
                    status = poll_res.get("Asset", {}).get("status", "")
                    
                status = str(status).lower()
                
                if status in ["ready", "success", "uploaded", "created", "active", "completed"]:'''

text = text.replace(old_code, new_code)
text = text.replace('max_polls = 20', 'max_polls = 60')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched GetAsset')
