import re

file_path = 'c:/AS/AIStory/backend/app/services/media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        if resp.status_code != 200:
            return {
                "checked": False,
                "blocked": moderation_required,
                "error": f"zlhub moderation failed {resp.status_code}",
                "details": (resp.text or "")[:1000],
                "submit_failed": moderation_required,
                "items": [],
            }

        try:
            response_payload = resp.json() if resp.content else {}
        except Exception:
            response_payload = {}'''

replacement = '''        if resp.status_code not in (200, 202):
            return {
                "checked": False,
                "blocked": moderation_required,
                "error": f"zlhub moderation failed {resp.status_code}",
                "details": (resp.text or "")[:1000],
                "submit_failed": moderation_required,
                "items": [],
            }

        try:
            response_payload = resp.json() if resp.content else {}
        except Exception:
            response_payload = {}
        
        if resp.status_code == 202 or "task_id" in response_payload:
            task_id = response_payload.get("task_id")
            if task_id:
                # Poll for completion
                import time
                import requests
                for _ in range(60):
                    time.sleep(3)
                    try:
                        poll_url = moderation_endpoint.replace("upload/async", f"task/{task_id}")
                        if "api/asset" in poll_url:
                            poll_url = poll_url.split("api/asset")[0] + f"api/task/{task_id}"
                        
                        poll_resp = requests.get(poll_url, headers=headers)
                        if poll_resp.status_code == 200:
                            poll_data = poll_resp.json()
                            if poll_data.get("status") in ("completed", "failed"):
                                response_payload = poll_data
                                break
                    except Exception:
                        pass
        '''

if target in text:
    print("Found 202 patch target!")
    text = text.replace(target, replacement)
else:
    print("Did not find 202 patch target.")


target_seedance = '"role": "first_frame" if idx == 0 else "reference_image",'
replacement_seedance = '"role": "reference_image",'
if target_seedance in text:
    print("Found seedance target!")
    # Only replace exactly in the loop we want
    parts = text.split("elif resolved_image_refs:")
    if len(parts) == 2:
        sub = parts[1].replace(target_seedance, replacement_seedance)
        text = parts[0] + "elif resolved_image_refs:" + sub
    else:
        text = text.replace(target_seedance, replacement_seedance)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Done patching.")
