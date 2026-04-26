import re
file_path = 'c:/AS/AIStory/backend/app/services/media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        if resp.status_code == 202 or "task_id" in response_payload:
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
                            poll_url = poll_url.split("api/asset")[0] + f"task/{task_id}"
                        
                        poll_resp = requests.get(poll_url, headers=headers)
                        if poll_resp.status_code == 200:'''

replacement = '''        if resp.status_code == 202 or "task_id" in response_payload:
            task_id = response_payload.get("task_id")
            if task_id:
                # Poll for completion
                import asyncio
                for _ in range(60):
                    await asyncio.sleep(3)
                    try:
                        poll_url = moderation_endpoint.replace("upload/async", f"task/{task_id}")
                        if "api/asset" in poll_url:
                            poll_url = poll_url.split("api/asset")[0] + f"task/{task_id}"
                        
                        poll_resp = await asyncio.to_thread(requests.get, poll_url, headers=headers)
                        if poll_resp.status_code == 200:'''

target2 = '''        if resp.status_code == 202 or "task_id" in response_payload:
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
                        if poll_resp.status_code == 200:'''

replacement2 = '''        if resp.status_code == 202 or "task_id" in response_payload:
            task_id = response_payload.get("task_id")
            if task_id:
                # Poll for completion
                import asyncio
                for _ in range(60):
                    await asyncio.sleep(3)
                    try:
                        poll_url = moderation_endpoint.replace("upload/async", f"task/{task_id}")
                        if "api/asset" in poll_url:
                            poll_url = poll_url.split("api/asset")[0] + f"api/task/{task_id}"
                        
                        poll_resp = await asyncio.to_thread(requests.get, poll_url, headers=headers)
                        if poll_resp.status_code == 200:'''


if target in text:
    text = text.replace(target, replacement)
    print("Patched target 1")
elif target2 in text:
    text = text.replace(target2, replacement2)
    print("Patched target 2")
else:
    print("Target not found")
    
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
